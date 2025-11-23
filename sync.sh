#!/bin/bash

# ==============================================================================
# Git Worktree Sync Script (Verbose)
# ==============================================================================

# Exit immediately if a command exits with a non-zero status
set -e
# Treat unset variables as an error
set -u

# ------------------------------------------------------------------------------
# Logging & Error Handling
# ------------------------------------------------------------------------------

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

log_info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
log_step()    { echo -e "${CYAN}[STEP]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warn()    { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $1"; }

# Error Trap: If the script fails, print the line number
trap 'log_error "Script failed unexpectedly on line $LINENO"' ERR

echo -e "--------------------------------------------------------"
echo -e "   Git Worktree Sync Tool"
echo -e "--------------------------------------------------------"

# ------------------------------------------------------------------------------
# 1. Validation & Discovery
# ------------------------------------------------------------------------------

log_step "Checking git environment..."

# Check if inside a git repo
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    log_error "Current directory is not part of a git repository."
    exit 1
fi

# Get Current Path and Branch
CURRENT_PATH=$(git rev-parse --show-toplevel)
# Handle potential detached HEAD in current directory gracefully
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "HEAD")

log_info "Current Directory: $CURRENT_PATH"
log_info "Current Branch:    $CURRENT_BRANCH"

log_step "Scanning for other worktrees..."

OTHER_PATH=""
OTHER_BRANCH=""
WORKTREE_COUNT=0

# Variables to track parsing state
parsing_path=""
parsing_branch=""

# We use --porcelain for robust parsing (handles paths with spaces)
while read -r line; do
    # Line format: "key value"
    key=$(echo "$line" | awk '{print $1}')
    value=$(echo "$line" | cut -d ' ' -f 2-)

    if [[ "$key" == "worktree" ]]; then
        # New worktree block detected
        ((WORKTREE_COUNT+=1))
        parsing_path="$value"
        log_info "Found worktree #$WORKTREE_COUNT at: $parsing_path"

    elif [[ "$key" == "branch" ]]; then
        # Branch associated with the current worktree block
        parsing_branch=${value#refs/heads/} # Strip refs/heads/
        
        if [[ "$parsing_path" != "$CURRENT_PATH" ]]; then
            OTHER_PATH="$parsing_path"
            OTHER_BRANCH="$parsing_branch"
            log_info "-> Identified as TARGET (Other) worktree."
        else
            log_info "-> Identified as CURRENT worktree."
        fi
    fi
done < <(git worktree list --porcelain)

# Validation
if [[ "$WORKTREE_COUNT" -ne 2 ]]; then
    log_error "Found $WORKTREE_COUNT worktrees. This script requires exactly 2 worktrees to function safely."
    exit 1
fi

if [[ -z "$OTHER_PATH" ]]; then
    log_error "Could not identify the 'other' worktree path."
    exit 1
fi

if [[ -z "$OTHER_BRANCH" ]] || [[ "$OTHER_BRANCH" == "HEAD" ]]; then
    log_error "The other worktree appears to be in a detached HEAD state. Cannot sync."
    exit 1
fi

echo ""
log_success "Ready to sync:"
echo -e "   Source (Current): ${GREEN}$CURRENT_BRANCH${NC} ($CURRENT_PATH)"
echo -e "   Target (Other):   ${GREEN}$OTHER_BRANCH${NC} ($OTHER_PATH)"
echo ""

# ------------------------------------------------------------------------------
# 2. Safety Checks (Uncommitted Changes)
# ------------------------------------------------------------------------------

log_step "Checking for uncommitted changes..."

if [[ -n "$(git status --porcelain)" ]]; then
    log_error "Your CURRENT worktree is dirty."
    git status --short
    exit 1
fi

if [[ -n "$(git -C "$OTHER_PATH" status --porcelain)" ]]; then
    log_error "The OTHER worktree is dirty."
    git -C "$OTHER_PATH" status --short
    exit 1
fi

log_success "Both worktrees are clean."

# ------------------------------------------------------------------------------
# 3. Rebase (Current onto Other)
# ------------------------------------------------------------------------------

log_step "Rebasing '$CURRENT_BRANCH' onto '$OTHER_BRANCH'..."

# Temporarily turn off 'set -e' to handle rebase failure manually
set +e
git rebase "$OTHER_BRANCH"
REBASE_STATUS=$?
set -e

if [ $REBASE_STATUS -eq 0 ]; then
    log_success "Rebase successful."
else
    log_error "Conflict detected during rebase!"
    log_warn "Aborting rebase..."
    git rebase --abort
    log_error "Sync aborted. Please resolve conflicts manually."
    exit 1
fi

# ------------------------------------------------------------------------------
# 4. Sync Other Worktree
# ------------------------------------------------------------------------------

log_step "Fast-forwarding '$OTHER_BRANCH'..."

# We execute the merge *in the context of the other directory*
if git -C "$OTHER_PATH" merge --ff-only "$CURRENT_BRANCH"; then
    NEW_HASH=$(git rev-parse --short HEAD)
    echo ""
    log_success "--------------------------------------------------------"
    log_success " DONE. Both branches synced to commit: $NEW_HASH"
    log_success "--------------------------------------------------------"
else
    log_error "Could not fast-forward the other worktree."
    log_warn "The history might have diverged in an unexpected way."
    exit 1
fi