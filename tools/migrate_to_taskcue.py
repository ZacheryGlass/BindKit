#!/usr/bin/env python3
"""
Migrate current repository to a new GitHub repo named BindKit, preserving data
while removing any references to "Claude" in issue titles, bodies, and comments.

What this script does:
- Creates a new repo (default name: BindKit) under your user.
- Pushes only the cleaned default branch (assumed: main) to the new repo.
- Copies labels and milestones.
- Transfers all issues (skips PRs), then scrubs "Claude" from titles/bodies/comments.
- Optionally migrates the wiki by cloning, scrubbing, and pushing it (if present).

What it cannot preserve (GitHub limitations):
- Pull Requests cannot be transferred. PR refs are not recreated; contributors from PRs will not appear in the new repo.
- Stars, forks, watchers, Actions history, and Releases are not transferred.
- Project boards and discussions are not handled.
- Editing issue/comment text updates the "updated_at" timestamp (original created timestamps remain).

Prerequisites:
- Python 3.9+
- Git installed and available on PATH
- Environment variable GITHUB_TOKEN with repo scope for your account
- Run from the root of the source repository working directory

Usage:
  python tools/migrate_to_taskcue.py \
    --source-owner ZacheryGlass \
    --source-repo Desktop-Utility-GUI \
    --target-owner ZacheryGlass \
    --target-repo BindKit \
    --default-branch main \
    [--private true|false] [--migrate-wiki]

Notes:
- By default this script creates the target repo as public if the source is public.
- If the target repo already exists, use --reuse-target to reuse it (it must be empty).

"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests


API = "https://api.github.com"


def die(msg: str, code: int = 1) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


_SENSITIVE_URL_RE = re.compile(r"https://[^\s/@:]+:[^\s@]*@github\.com/")


def _sanitize_args_for_log(args: List[str]) -> str:
    shown: List[str] = []
    for a in args:
        shown.append(_SENSITIVE_URL_RE.sub("https://***@github.com/", a))
    return " ".join(shown)


def run(cmd: List[str], cwd: Optional[str] = None, check: bool = True) -> subprocess.CompletedProcess:
    print("$", _sanitize_args_for_log(cmd))
    return subprocess.run(cmd, cwd=cwd, check=check)


def run_capture(cmd: List[str], cwd: Optional[str] = None) -> str:
    print("$", _sanitize_args_for_log(cmd))
    out = subprocess.check_output(cmd, cwd=cwd)
    return out.decode().strip()


def gh_request(method: str, url: str, token: str, **kwargs) -> requests.Response:
    headers = kwargs.pop("headers", {})
    headers.setdefault("Authorization", f"Bearer {token}")
    headers.setdefault("Accept", "application/vnd.github+json")
    headers.setdefault("X-GitHub-Api-Version", "2022-11-28")
    resp = requests.request(method, url, headers=headers, timeout=30, **kwargs)
    if resp.status_code >= 400:
        try:
            data = resp.json()
        except Exception:
            data = resp.text
        die(f"GitHub API {method} {url} failed: {resp.status_code} {data}")
    return resp


def gh_paginate(url: str, token: str, params: Optional[Dict[str, Any]] = None) -> Iterable[Dict[str, Any]]:
    params = dict(params or {})
    params.setdefault("per_page", 100)
    page_url = url
    while True:
        resp = gh_request("GET", page_url, token, params=params)
        items = resp.json()
        if not isinstance(items, list):
            die(f"Expected list from {page_url}, got {type(items)}")
        for it in items:
            yield it
        link = resp.headers.get("Link", "")
        next_url = None
        if link:
            parts = [p.strip() for p in link.split(",")]
            for p in parts:
                if 'rel="next"' in p:
                    m = re.search(r"<([^>]+)>", p)
                    if m:
                        next_url = m.group(1)
                        break
        if not next_url:
            break
        page_url = next_url
        params = {}  # already encoded in next_url


def sanitize_text(text: Optional[str]) -> Optional[str]:
    if text is None:
        return None
    # Remove various references to Claude (case-insensitive)
    patterns = [
        r"@claude\b",            # remove handle
        r"claude\[bot\]",       # remove bot label
        r"claude\s*code",        # remove 'Claude Code'
        r"\banthropic\b",       # remove 'Anthropic' as a word
        # remove only the specific co-author trailer line
        r"^co-\s*authored-\s*by:\s*claude.*$",
        # fallback: remove 'claude' as a whole word
        r"\bclaude\b",
    ]
    result = text
    for pat in patterns:
        result = re.sub(pat, "", result, flags=re.IGNORECASE | re.MULTILINE)
    # Collapse repeated spaces/newlines introduced by removal
    result = re.sub(r"[ \t]{2,}", " ", result)
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()


@dataclass
class RepoInfo:
    owner: str
    name: str
    private: bool
    description: Optional[str]
    has_issues: bool
    has_projects: bool
    has_wiki: bool
    default_branch: str


def get_repo_info(owner: str, repo: str, token: str) -> RepoInfo:
    url = f"{API}/repos/{owner}/{repo}"
    r = gh_request("GET", url, token)
    j = r.json()
    return RepoInfo(
        owner=owner,
        name=repo,
        private=bool(j.get("private", False)),
        description=j.get("description"),
        has_issues=bool(j.get("has_issues", True)),
        has_projects=bool(j.get("has_projects", True)),
        has_wiki=bool(j.get("has_wiki", False)),
        default_branch=j.get("default_branch", "main"),
    )


def ensure_target_repo(owner: str, name: str, token: str, src: RepoInfo, reuse: bool, private: Optional[bool]) -> None:
    # Check if target exists
    exists = False
    url = f"{API}/repos/{owner}/{name}"
    resp = requests.get(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }, timeout=30)
    if resp.status_code == 200:
        exists = True
        if not reuse:
            die(f"Target repo {owner}/{name} already exists. Use --reuse-target to reuse it.")
    elif resp.status_code != 404:
        die(f"Failed to check target repo existence: {resp.status_code} {resp.text}")

    if exists:
        print(f"Target repo {owner}/{name} exists; reusing as requested.")
        return

    # Create new repo under user
    desc = sanitize_text(src.description or "")
    payload = {
        "name": name,
        "description": desc or None,
        "private": bool(src.private) if private is None else bool(private),
        "has_issues": True,
        "has_projects": src.has_projects,
        "has_wiki": src.has_wiki,
        "auto_init": False,
    }
    r = gh_request("POST", f"{API}/user/repos", token, json=payload)
    print(f"Created target repo: {r.json().get('full_name')}")


def _git_ref_exists(ref: str) -> bool:
    try:
        subprocess.run(["git", "show-ref", "--verify", "--quiet", ref], check=False)
        # show-ref --verify returns 0 if exists, 1 if not
        return subprocess.call(["git", "show-ref", "--verify", "--quiet", ref]) == 0
    except Exception:
        return False


def git_push_main_to_target(target_owner: str, target_repo: str, token: str, default_branch: str) -> None:
    # Add a temporary remote with token in URL for auth
    remote_name = "bindkit"
    remote_url = f"https://{token}:x-oauth-basic@github.com/{target_owner}/{target_repo}.git"

    # If remote exists, remove
    remotes = run_capture(["git", "remote"]).splitlines()
    if remote_name in remotes:
        run(["git", "remote", "remove", remote_name])

    run(["git", "remote", "add", remote_name, remote_url])
    try:
        # Determine source ref to push
        src_ref = default_branch
        if not _git_ref_exists(f"refs/heads/{default_branch}"):
            # Fallback to current branch or HEAD
            try:
                current = run_capture(["git", "rev-parse", "--abbrev-ref", "HEAD"]) or "HEAD"
            except subprocess.CalledProcessError:
                die(f"Cannot determine current branch; ensure you're in a git repo with commits.")
            if current and current != "HEAD" and _git_ref_exists(f"refs/heads/{current}"):
                print(f"Local branch '{default_branch}' not found; pushing current branch '{current}' to '{default_branch}'.")
                src_ref = current
            else:
                print(f"Local branch '{default_branch}' not found; pushing HEAD to '{default_branch}'.")
                src_ref = "HEAD"

        # Push src_ref to target default branch name
        run(["git", "push", "-u", remote_name, f"{src_ref}:{default_branch}"])
    finally:
        # Clean up remote to avoid leaking token in config
        run(["git", "remote", "remove", remote_name])


def copy_labels(src_owner: str, src_repo: str, dst_owner: str, dst_repo: str, token: str) -> None:
    print("Copying labels...")
    labels = list(gh_paginate(f"{API}/repos/{src_owner}/{src_repo}/labels", token))
    for lbl in labels:
        data = {
            "name": lbl.get("name"),
            "color": lbl.get("color"),
            "description": sanitize_text(lbl.get("description")),
        }
        # Try create; if conflicts, attempt update
        create_url = f"{API}/repos/{dst_owner}/{dst_repo}/labels"
        r = requests.post(create_url, headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }, json=data, timeout=30)
        if r.status_code == 201:
            print(f"  + label {data['name']}")
            continue
        if r.status_code == 422:
            # Already exists; update
            upd = gh_request("PATCH", f"{API}/repos/{dst_owner}/{dst_repo}/labels/{data['name']}", token, json=data)
            print(f"  ~ label {data['name']}")
        else:
            die(f"Failed to create label {data['name']}: {r.status_code} {r.text}")


def copy_milestones(src_owner: str, src_repo: str, dst_owner: str, dst_repo: str, token: str) -> Dict[int, int]:
    print("Copying milestones...")
    src_milestones = list(gh_paginate(f"{API}/repos/{src_owner}/{src_repo}/milestones", token, params={"state": "all"}))
    number_map: Dict[int, int] = {}
    for m in src_milestones:
        data = {
            "title": m.get("title"),
            "state": m.get("state", "open"),
            "description": sanitize_text(m.get("description")),
            "due_on": m.get("due_on"),
        }
        r = gh_request("POST", f"{API}/repos/{dst_owner}/{dst_repo}/milestones", token, json=data)
        new = r.json()
        number_map[m.get("number")] = new.get("number")
        print(f"  + milestone {data['title']} -> #{new.get('number')}")
    return number_map


def _create_issue(dst_owner: str, dst_repo: str, token: str, *, title: str, body: Optional[str], labels: List[str], milestone: Optional[int], assignees: List[str]) -> int:
    data: Dict[str, Any] = {"title": title}
    if body is not None:
        data["body"] = body
    if labels:
        data["labels"] = labels
    if milestone:
        data["milestone"] = milestone
    if assignees:
        data["assignees"] = assignees
    r = gh_request("POST", f"{API}/repos/{dst_owner}/{dst_repo}/issues", token, json=data)
    return int(r.json()["number"])  # type: ignore[index]


def _copy_issue_fallback(src_owner: str, src_repo: str, src_issue: Dict[str, Any], dst_owner: str, dst_repo: str, token: str, milestone_map: Dict[int, int]) -> Optional[int]:
    num = int(src_issue.get("number"))
    title = sanitize_text(src_issue.get("title") or "") or (src_issue.get("title") or "")
    body = sanitize_text(src_issue.get("body") or "")
    author = src_issue.get("user", {}).get("login", "unknown")
    created_at = src_issue.get("created_at", "")
    src_url = src_issue.get("html_url", f"https://github.com/{src_owner}/{src_repo}/issues/{num}")
    meta = f"\n\n---\nMigrated from {src_owner}/{src_repo}#{num} (opened by @{author} on {created_at}).\n"
    body_final = (body or "") + meta
    labels = [lbl.get("name") for lbl in (src_issue.get("labels") or []) if isinstance(lbl, dict) and lbl.get("name")]
    assignees = [a.get("login") for a in (src_issue.get("assignees") or []) if isinstance(a, dict) and a.get("login")]
    milestone_src_num = src_issue.get("milestone", {}) or {}
    milestone_dst = None
    if isinstance(milestone_src_num, dict) and milestone_src_num.get("number") is not None:
        milestone_dst = milestone_map.get(int(milestone_src_num.get("number")))

    try:
        new_num = _create_issue(dst_owner, dst_repo, token, title=title, body=body_final, labels=labels, milestone=milestone_dst, assignees=assignees)
        print(f"  + copied issue #{num} -> #{new_num}")
    except SystemExit:
        print(f"  ! failed to copy issue #{num}; skipping")
        return None

    # Copy comments
    comments_url = f"{API}/repos/{src_owner}/{src_repo}/issues/{num}/comments"
    comments = list(gh_paginate(comments_url, token))
    for c in comments:
        cid = c.get("id")
        cuser = c.get("user", {}).get("login", "unknown")
        ctime = c.get("created_at", "")
        cbody = sanitize_text(c.get("body") or "") or ""
        cbody_final = f"{cbody}\n\n_(originally commented by @{cuser} on {ctime})_"
        try:
            gh_request("POST", f"{API}/repos/{dst_owner}/{dst_repo}/issues/{new_num}/comments", token, json={"body": cbody_final})
            print(f"    ~ copied comment {cid}")
        except SystemExit:
            print(f"    ! failed to copy comment {cid}")

    # Close the new issue if the source is closed
    if (src_issue.get("state") == "closed"):
        state_reason = src_issue.get("state_reason")
        payload: Dict[str, Any] = {"state": "closed"}
        if state_reason in ("completed", "not_planned"):
            payload["state_reason"] = state_reason
        try:
            gh_request("PATCH", f"{API}/repos/{dst_owner}/{dst_repo}/issues/{new_num}", token, json=payload)
        except SystemExit:
            pass
    return new_num


def transfer_issue(src_owner: str, src_repo: str, issue_number: int, dst_owner: str, dst_repo: str, token: str) -> Optional[int]:
    url = f"{API}/repos/{src_owner}/{src_repo}/issues/{issue_number}/transfer"
    payload = {"new_repository": f"{dst_owner}/{dst_repo}"}
    try:
        r = gh_request("POST", url, token, json=payload)
        new_issue = r.json().get("issue", {})
        new_number = new_issue.get("number")
        print(f"  # {issue_number} -> {new_number}")
        return int(new_number) if new_number is not None else None
    except SystemExit as e:
        # Surface transfer failure by returning None and let caller handle fallback
        print(f"  ! transfer failed for issue #{issue_number}; will try copy fallback")
        return None


def scrub_issue(dst_owner: str, dst_repo: str, issue_number: int, token: str) -> None:
    # Get issue
    r = gh_request("GET", f"{API}/repos/{dst_owner}/{dst_repo}/issues/{issue_number}", token)
    issue = r.json()
    title = issue.get("title")
    body = issue.get("body")
    new_title = sanitize_text(title) or title
    new_body = sanitize_text(body) if body is not None else body
    if new_title != title or new_body != body:
        gh_request(
            "PATCH",
            f"{API}/repos/{dst_owner}/{dst_repo}/issues/{issue_number}",
            token,
            json={"title": new_title, "body": new_body},
        )
        print(f"    ~ scrubbed issue #{issue_number}")

    # Scrub all comments
    comments = list(gh_paginate(f"{API}/repos/{dst_owner}/{dst_repo}/issues/{issue_number}/comments", token))
    for c in comments:
        cid = c.get("id")
        body = c.get("body")
        new_body = sanitize_text(body)
        if new_body is not None and new_body != body:
            gh_request(
                "PATCH",
                f"{API}/repos/{dst_owner}/{dst_repo}/issues/comments/{cid}",
                token,
                json={"body": new_body},
            )
            print(f"      ~ comment {cid} scrubbed")


def migrate_wiki_if_present(src_owner: str, src_repo: str, dst_owner: str, dst_repo: str, token: str) -> None:
    print("Checking for wiki...")
    # Check if wiki has content by attempting to clone
    src_wiki_url = f"https://github.com/{src_owner}/{src_repo}.wiki.git"
    tmpdir = tempfile.mkdtemp(prefix="wiki-")
    try:
        try:
            run(["git", "clone", "--quiet", src_wiki_url, tmpdir])
        except subprocess.CalledProcessError:
            print("No wiki repository found or not accessible; skipping wiki migration.")
            return

        # If empty, skip
        files = os.listdir(tmpdir)
        if not files:
            print("Wiki repository is empty; skipping.")
            return

        # Scrub 'Claude' references across text files
        for root, _, filenames in os.walk(tmpdir):
            for fn in filenames:
                path = os.path.join(root, fn)
                # Only scrub text-like files
                try:
                    with open(path, "rb") as f:
                        data = f.read()
                    try:
                        text = data.decode("utf-8")
                    except UnicodeDecodeError:
                        continue
                    new_text = sanitize_text(text)
                    if new_text != text:
                        with open(path, "w", encoding="utf-8", newline="") as f:
                            f.write(new_text)
                except Exception:
                    continue

        # Push to destination wiki
        dst_wiki_url = f"https://{token}:x-oauth-basic@github.com/{dst_owner}/{dst_repo}.wiki.git"
        run(["git", "-C", tmpdir, "remote", "remove", "origin"], check=False)
        run(["git", "-C", tmpdir, "remote", "add", "origin", dst_wiki_url])
        run(["git", "-C", tmpdir, "push", "-u", "origin", "master"], check=False)
        run(["git", "-C", tmpdir, "push", "-u", "origin", "main"], check=False)
        print("Wiki migration attempted (if destination wiki enabled).")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate repo to new TaskCue repo and scrub 'Claude' references.")
    parser.add_argument("--source-owner", required=True)
    parser.add_argument("--source-repo", required=True)
    parser.add_argument("--target-owner", required=True)
    parser.add_argument("--target-repo", default="BindKit")
    parser.add_argument("--default-branch", default="main")
    parser.add_argument("--private", choices=["true", "false"], default=None, help="Override target repo privacy")
    parser.add_argument("--reuse-target", action="store_true", help="Reuse existing empty target repo if present")
    parser.add_argument("--migrate-wiki", action="store_true", help="Attempt to migrate and scrub wiki content")
    parser.add_argument("--skip-push", action="store_true", help="Skip pushing code; only migrate metadata")
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        die("GITHUB_TOKEN environment variable is required.")

    src = get_repo_info(args.source_owner, args.source_repo, token)
    ensure_target_repo(
        args.target_owner,
        args.target_repo,
        token,
        src,
        reuse=args.reuse_target,
        private=(None if args.private is None else args.private.lower() == "true"),
    )

    # Push only the default branch (assumed clean of Claude co-authors/commits)
    if not args.skip_push:
        git_push_main_to_target(args.target_owner, args.target_repo, token, args.default_branch)
    else:
        print("Skipping code push as requested (--skip-push).")

    # Copy labels and milestones first so transfers keep associations
    copy_labels(args.source_owner, args.source_repo, args.target_owner, args.target_repo, token)
    milestone_map = copy_milestones(args.source_owner, args.source_repo, args.target_owner, args.target_repo, token)

    # Fetch all issues (not PRs) and transfer them
    print("Transferring issues and scrubbing content...")
    issues = list(gh_paginate(
        f"{API}/repos/{args.source_owner}/{args.source_repo}/issues",
        token,
        params={"state": "all"},
    ))

    non_pr_issues = [i for i in issues if "pull_request" not in i]
    for it in non_pr_issues:
        old_num = int(it.get("number"))
        new_num = transfer_issue(args.source_owner, args.source_repo, old_num, args.target_owner, args.target_repo, token)
        if new_num is None:
            # Use fallback copy approach
            new_num = _copy_issue_fallback(args.source_owner, args.source_repo, it, args.target_owner, args.target_repo, token, milestone_map)
            if new_num is None:
                continue
        # Scrub title, body, and comments in the new repo (extra safety)
        try:
            scrub_issue(args.target_owner, args.target_repo, new_num, token)
        except SystemExit:
            raise
        except Exception as e:
            print(f"  ! failed to scrub issue #{new_num}: {e}")

    if args.migrate_wiki and src.has_wiki:
        migrate_wiki_if_present(args.source_owner, args.source_repo, args.target_owner, args.target_repo, token)

    print("Migration complete.")


if __name__ == "__main__":
    main()
