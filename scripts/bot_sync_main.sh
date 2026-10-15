#!/usr/bin/env bash
# Sync a bot's working tree with the LATEST upstream `main` before it starts work (issue #303).
#
# Why: the implementer used to open a PR from whatever `actions/checkout` had when the run began,
# and the fix-bot repaired a branch without ever looking at main. Both could therefore do correct
# work on a stale base - and a reviewer's first remark was always "rebase this".
#
#   reset   before implementing a NEW issue: hard-reset the tree to origin/main, so the branch the
#           bot pushes is based on latest main.
#   rebase  before repairing an EXISTING PR: rebase the checked-out branch onto origin/main.
#           A conflict is NOT resolved here - that is the rebase-bot's job (#246). It is reported
#           and the caller leaves the PR alone; exit 2 means "synced base refused, not an error in
#           the repair itself".
#
# Exit codes: 0 synced, 2 the sync conflicts (leave it to the rebase-bot), anything else = failure.
# A remote that cannot be reached is always a failure: a bot must never work from a stale base.
set -euo pipefail

REMOTE="${BOT_SYNC_REMOTE:-origin}"
BRANCH="${BOT_SYNC_BRANCH:-main}"
MODE="${1:-}"

say() { printf '[bot-sync] %s\n' "$*"; }
die() { printf '[bot-sync] ERROR: %s\n' "$*" >&2; exit 1; }

case "$MODE" in
  reset|rebase) ;;
  *) die "usage: $0 {reset|rebase} (got '${MODE}')" ;;
esac

git rev-parse --git-dir >/dev/null 2>&1 || die "not inside a git repository"

# 1. the remote must answer. A bot that cannot see main must NOT start.
if ! git fetch "$REMOTE" "$BRANCH" --quiet 2>/dev/null; then
  die "cannot fetch ${REMOTE}/${BRANCH} - refusing to start on a stale base"
fi
TARGET="$(git rev-parse --verify --quiet "FETCH_HEAD")" \
  || die "cannot resolve ${REMOTE}/${BRANCH} after fetching it"
say "fetched ${REMOTE}/${BRANCH} ($(git rev-parse --short "$TARGET"))"

if [ "$MODE" = "reset" ]; then
  # 2a. implementing something new: the tree becomes exactly latest main.
  git reset --hard --quiet "$TARGET"
  say "reset the working tree to ${REMOTE}/${BRANCH} (new work starts from latest main)"
  exit 0
fi

# 2b. repairing an existing PR: replay this branch's own commits on top of latest main.
HEAD_REF="$(git symbolic-ref --quiet --short HEAD || true)"
[ -n "$HEAD_REF" ] || die "detached HEAD: a repair needs the PR's branch checked out"

if git merge-base --is-ancestor "$TARGET" HEAD; then
  say "${HEAD_REF} already contains ${REMOTE}/${BRANCH}: nothing to sync"
  exit 0
fi

BEFORE="$(git rev-parse HEAD)"
# rerere OFF: a recorded resolution from an earlier rebase is not trustworthy here (issue #246).
set +e
git -c rerere.enabled=false rebase "$TARGET" >/dev/null 2>&1
rc=$?
set -e
if [ "$rc" -ne 0 ]; then
  git rebase --abort >/dev/null 2>&1 || true
  [ "$(git rev-parse HEAD)" = "$BEFORE" ] || die "aborted a conflicted rebase but HEAD moved"
  printf '[bot-sync] %s does not rebase cleanly onto %s/%s: leaving it to the rebase-bot (issue #246)\n' \
    "$HEAD_REF" "$REMOTE" "$BRANCH" >&2
  exit 2
fi
say "${HEAD_REF}: rebased $(git rev-list --count "$BEFORE..HEAD" 2>/dev/null || echo '?') commit(s) onto ${REMOTE}/${BRANCH}"
exit 0
