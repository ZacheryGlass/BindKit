Here’s a single-file Python watcher that keeps one or more untracked files synced across `dev`, `dev2`, `dev3`, `dev4`. No external deps. Polls, debounces writes, resolves conflicts by “newest wins,” copies atomically, optional backups, multi-file support. Put it anywhere and run.

```python
#!/usr/bin/env python3
"""
Sync specified untracked files across 4 parallel working copies in the same repo.

Usage:
  1) Set config below: GIT_ROOT_PATH, REPO_DIRS, FILES_TO_SYNC.
  2) Run: python sync_untracked.py
Notes:
  - “Newest wins” conflict policy (by mtime; deterministic tie-break by repo order).
  - Debounce writes with QUIET_PERIOD_SECONDS to avoid syncing half-written files.
  - Atomic replace on target to avoid partial writes.
  - By default, deletions do NOT propagate (files are “healed” from another copy).
"""

import os
import time
import shutil
import hashlib
import tempfile
from dataclasses import dataclass
from typing import List, Optional, Tuple

# =========================
# CONFIG
# =========================
GIT_ROOT_PATH = r"/absolute/path/to/GIT_ROOT_PATH"  # Edit this
REPO_DIRS: List[str] = ["dev", "dev2", "dev3", "dev4"]  # Order = priority on exact ties
FILES_TO_SYNC: List[str] = [
    # Paths are relative to each repo root
    # Example:
    # "local_config.ini",
    # "tools/my_untracked.json",
]

POLL_INTERVAL_SECONDS = 0.75        # How often to scan
QUIET_PERIOD_SECONDS = 0.75         # Source file must be unchanged for at least this long
PRESERVE_BACKUPS = True             # If True, keep a timestamped .bak before overwrite
ALLOW_DELETE_PROPAGATION = False    # If True, deleting in one repo deletes in others

# =========================
# END CONFIG
# =========================


@dataclass
class FileInfo:
    exists: bool
    path: str
    size: int = 0
    mtime_ns: int = 0
    sha256: Optional[str] = None  # Filled lazily when needed


def abs_repo_paths() -> List[str]:
    return [os.path.normpath(os.path.join(GIT_ROOT_PATH, d)) for d in REPO_DIRS]


def ensure_repos_exist(repo_paths: List[str]) -> None:
    missing = [p for p in repo_paths if not os.path.isdir(p)]
    if missing:
        raise SystemExit(f"Repo directories not found: {missing}")


def stat_file(path: str) -> FileInfo:
    try:
        st = os.stat(path)
        return FileInfo(True, path, st.st_size, st.st_mtime_ns, None)
    except FileNotFoundError:
        return FileInfo(False, path)


def sha256_of(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def now_monotonic() -> float:
    return time.monotonic()


def atomic_write_bytes(dest_path: str, data: bytes) -> None:
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    d = os.path.dirname(dest_path) or "."
    with tempfile.NamedTemporaryFile(dir=d, delete=False) as tmp:
        tmp.write(data)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp_name = tmp.name
    # Preserve source times via copystat is handled outside. Here we just replace atomically.
    os.replace(tmp_name, dest_path)


def read_bytes(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def backup_if_needed(dest_path: str) -> None:
    if not PRESERVE_BACKUPS or not os.path.exists(dest_path):
        return
    ts = time.strftime("%Y%m%d-%H%M%S")
    bak = f"{dest_path}.bak.{ts}"
    try:
        shutil.copy2(dest_path, bak)
    except Exception as e:
        print(f"[warn] Failed to create backup for {dest_path}: {e}")


def pick_source(infos: List[FileInfo]) -> Optional[int]:
    """
    Pick source index by latest mtime among existing. Tie-break by repo order (lower index wins).
    Returns None if no copies exist.
    """
    candidates: List[Tuple[int, int]] = []  # (index, mtime_ns)
    for i, fi in enumerate(infos):
        if fi.exists:
            candidates.append((i, fi.mtime_ns))
    if not candidates:
        return None
    # Max by mtime_ns, then stable order via REPO_DIRS order
    max_mtime = max(m for _, m in candidates)
    for i, m in candidates:
        if m == max_mtime:
            return i
    return candidates[0][0]


def all_same_hash(infos: List[FileInfo]) -> bool:
    hashes = set(fi.sha256 for fi in infos if fi.exists)
    return len(hashes) <= 1


def main() -> None:
    if not FILES_TO_SYNC:
        raise SystemExit("FILES_TO_SYNC is empty. Configure it at the top of the script.")

    repo_paths = abs_repo_paths()
    ensure_repos_exist(repo_paths)

    # Track last observed mtimes to implement quiet-period gating
    # key: (relpath, repo_idx) -> last_seen_mtime_ns
    last_seen_mtime = {}
    # key: (relpath, repo_idx) -> last_change_monotonic_time
    changed_at = {}

    # Initialize
    t0 = now_monotonic()
    for rel in FILES_TO_SYNC:
        for i, rp in enumerate(repo_paths):
            ap = os.path.join(rp, rel)
            fi = stat_file(ap)
            last_seen_mtime[(rel, i)] = fi.mtime_ns if fi.exists else 0
            # initialize as “old” so first stable source can sync immediately
            changed_at[(rel, i)] = t0 - (QUIET_PERIOD_SECONDS * 2)

    print(f"[info] Syncing across repos: {', '.join(repo_paths)}")
    print(f"[info] Files: {', '.join(FILES_TO_SYNC)}")
    print("[info] Ctrl-C to stop.")

    try:
        while True:
            loop_start = now_monotonic()
            for rel in FILES_TO_SYNC:
                infos: List[FileInfo] = []
                for i, rp in enumerate(repo_paths):
                    ap = os.path.join(rp, rel)
                    fi = stat_file(ap)
                    # update change detection
                    prev_m = last_seen_mtime.get((rel, i), 0)
                    if fi.exists and fi.mtime_ns != prev_m:
                        changed_at[(rel, i)] = loop_start
                        last_seen_mtime[(rel, i)] = fi.mtime_ns
                    elif not fi.exists and prev_m != 0:
                        # file disappeared in this repo
                        changed_at[(rel, i)] = loop_start
                        last_seen_mtime[(rel, i)] = 0
                    infos.append(fi)

                # If nothing exists anywhere, nothing to do yet
                if not any(fi.exists for fi in infos):
                    continue

                # If delete propagation is disabled, ignore deletions as “sources”
                # Build list of candidate sources that actually exist
                src_idx = pick_source(infos)
                if src_idx is None:
                    continue

                # Quiet period gating for the would-be source
                src_quiet_ok = (loop_start - changed_at[(rel, src_idx)]) >= QUIET_PERIOD_SECONDS
                if not src_quiet_ok:
                    continue

                # Compute hashes only if needed
                # If any size/mtime differ, we need to resolve
                sizes = [fi.size for fi in infos if fi.exists]
                mtimes = [fi.mtime_ns for fi in infos if fi.exists]
                need_hash = len(set(sizes)) > 1 or len(set(mtimes)) > 1

                if need_hash:
                    for fi in infos:
                        if fi.exists and fi.sha256 is None:
                            try:
                                fi.sha256 = sha256_of(fi.path)
                            except Exception as e:
                                print(f"[warn] Hash failed for {fi.path}: {e}")
                                fi.sha256 = None
                else:
                    # sizes and mtimes identical; compute one hash to verify sameness
                    any_existing = next((fi for fi in infos if fi.exists), None)
                    if any_existing:
                        h = sha256_of(any_existing.path)
                        for fi in infos:
                            if fi.exists:
                                fi.sha256 = h

                # If all copies equal, continue
                if all_same_hash(infos):
                    continue

                # Resolve source among existing copies again, but prefer the newest hash-bearing one
                # If equal mtime, first in REPO_DIRS wins.
                src_idx = pick_source(infos)
                if src_idx is None or not infos[src_idx].exists:
                    continue

                # Optional: do not propagate deletions unless allowed
                if not ALLOW_DELETE_PROPAGATION and not infos[src_idx].exists:
                    # If the “newest” is a deletion, pick the newest existing instead
                    existing_idxs = [i for i, fi in enumerate(infos) if fi.exists]
                    if not existing_idxs:
                        continue
                    # Choose newest among existing
                    src_idx = max(existing_idxs, key=lambda i: infos[i].mtime_ns)

                src = infos[src_idx]
                if not src.exists:
                    # All missing or deletion chosen while not allowed
                    continue

                # Read source bytes once
                try:
                    src_bytes = read_bytes(src.path)
                except Exception as e:
                    print(f"[warn] Read failed for {src.path}: {e}")
                    continue

                # Propagate to others where content differs or file missing
                for i, fi in enumerate(infos):
                    if i == src_idx:
                        continue

                    # Delete propagation
                    if ALLOW_DELETE_PROPAGATION and not src.exists and fi.exists:
                        try:
                            if os.path.isfile(fi.path):
                                os.remove(fi.path)
                                print(f"[del ] {REPO_DIRS[i]}:{rel}")
                                last_seen_mtime[(rel, i)] = 0
                                changed_at[(rel, i)] = now_monotonic()
                        except Exception as e:
                            print(f"[warn] Delete failed {fi.path}: {e}")
                        continue

                    # Skip if equal hash
                    equal = fi.exists and fi.sha256 == infos[src_idx].sha256 and fi.sha256 is not None
                    if equal:
                        continue

                    # Write
                    try:
                        if PRESERVE_BACKUPS and fi.exists:
                            backup_if_needed(fi.path)
                        atomic_write_bytes(fi.path, src_bytes)
                        # Copy timestamps from source to dest
                        try:
                            st = os.stat(src.path)
                            os.utime(fi.path, ns=(st.st_atime_ns, st.st_mtime_ns))
                            last_seen_mtime[(rel, i)] = st.st_mtime_ns
                        except Exception:
                            # Fall back: mark current time
                            last_seen_mtime[(rel, i)] = os.stat(fi.path).st_mtime_ns
                        changed_at[(rel, i)] = now_monotonic()
                        print(f"[sync] {REPO_DIRS[src_idx]} -> {REPO_DIRS[i]} : {rel}")
                    except Exception as e:
                        print(f"[error] Write failed to {fi.path}: {e}")

            # Sleep until next poll
            elapsed = now_monotonic() - loop_start
            to_sleep = POLL_INTERVAL_SECONDS - elapsed
            if to_sleep > 0:
                time.sleep(to_sleep)

    except KeyboardInterrupt:
        print("\n[info] Stopped.")


if __name__ == "__main__":
    main()
```
