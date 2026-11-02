#!/usr/bin/env bash
# Shared helpers for case scaffold scripts. A scaffold sources this file:
#   . "$(dirname "${BASH_SOURCE[0]}")/../../tools/workspace.sh"
# claude plugin eval runs scaffolds in the empty run workspace, as the operator,
# with HOME set to a temporary directory and no git identity configured.
set -euo pipefail

EVALS_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
REPO_CACHE="$EVALS_DIR/.cache/repos"
HISTORY_CACHE="$EVALS_DIR/.cache/history"
FIXTURES="$EVALS_DIR/fixtures"

# setup_repo NAME [OVERLAY_DIR]
# Clones $REPO_CACHE/NAME into ./NAME. If OVERLAY_DIR/NAME exists, copies its files over
# the clone and folds them into the existing root commit, keeping the original author,
# committer and dates, so neither git status nor git log shows which files were added.
setup_repo() {
  local name=$1 overlay=${2:-}
  git clone --quiet --no-hardlinks "$REPO_CACHE/$name" "$name" 2>/dev/null
  git -C "$name" remote remove origin 2>/dev/null || true
  if [ -n "$overlay" ] && [ -d "$overlay/$name" ]; then
    cp -R "$overlay/$name/." "$name/"
    fold_into_head "$name"
  fi
}

# setup_history_repo NAME BRANCH [DEFAULT_BRANCH]
# Clones branch BRANCH of $HISTORY_CACHE/NAME into ./NAME with its whole commit history but only the
# file contents of its tip (--filter=blob:none), renames the branch to DEFAULT_BRANCH (master), and
# drops the remote and the reflog, so later commits (the real fix) and the cache path stay hidden.
setup_history_repo() {
  local name=$1 branch=$2 default=${3:-master}
  git -c protocol.file.allow=always clone --quiet --no-local --filter=blob:none --single-branch \
    --branch "$branch" "file://$HISTORY_CACHE/$name" "$name" 2>/dev/null
  git -C "$name" branch -q -m "$default"
  git -C "$name" remote remove origin
  git -C "$name" reflog expire --expire=now --all
}

# setup_fixture NAME: copies $FIXTURES/NAME into the workspace root as a one-commit git repo.
setup_fixture() {
  local name=$1
  cp -R "$FIXTURES/$name/." .
  git init --quiet -b main .
  git add -A
  git -c user.name=dev -c user.email=dev@example.com commit --quiet -m "init"
}

fold_into_head() {
  local dir=$1
  local an ae ad cn ce cd
  an=$(git -C "$dir" log -1 --format=%an); ae=$(git -C "$dir" log -1 --format=%ae); ad=$(git -C "$dir" log -1 --format=%aI)
  cn=$(git -C "$dir" log -1 --format=%cn); ce=$(git -C "$dir" log -1 --format=%ce); cd=$(git -C "$dir" log -1 --format=%cI)
  git -C "$dir" add -A
  GIT_AUTHOR_NAME="$an" GIT_AUTHOR_EMAIL="$ae" GIT_AUTHOR_DATE="$ad" \
  GIT_COMMITTER_NAME="$cn" GIT_COMMITTER_EMAIL="$ce" GIT_COMMITTER_DATE="$cd" \
    git -C "$dir" commit --quiet --amend --no-edit --allow-empty
  git -C "$dir" reflog expire --expire=now --all
  git -C "$dir" gc --quiet --prune=now
}
