#!/usr/bin/env bash
# Enumerate a PR's merge state and, only when it is genuinely CONFLICTING, the exact files
# that conflict with the current origin/main. Prints nothing destructive; deletes its temp ref.
#
#   scripts/conflict-files.sh <pr-number> [repo] [remote]
#
# "Behind main" is NOT a rebase trigger — this exits early for MERGEABLE/UNKNOWN PRs.
set -euo pipefail

N=${1:?usage: conflict-files.sh <pr> [repo] [remote]}
REPO=${2:-asimov-agent/llgenie}
REMOTE=${3:-origin}

gh pr view "$N" -R "$REPO" --json number,headRefName,baseRefName,mergeable,mergeStateStatus \
  --jq '"#\(.number) \(.headRefName) base=\(.baseRefName) mergeable=\(.mergeable) ms=\(.mergeStateStatus)"'

STATE=$(gh pr view "$N" -R "$REPO" --json mergeable --jq .mergeable)
if [ "$STATE" != "CONFLICTING" ]; then
  echo "mergeable=$STATE -> no rebase owed (behind main is not a trigger)"
  exit 0
fi

TMP="tmp-conflict-$N"
git fetch "$REMOTE" main --quiet
git fetch "$REMOTE" "pull/$N/head:refs/heads/$TMP" --quiet
BASE=$(git merge-base "$REMOTE/main" "$TMP")
echo "== changed in both, base=$(git rev-parse --short "$BASE") vs $REMOTE/main=$(git rev-parse --short "$REMOTE/main") =="
git merge-tree "$BASE" "$REMOTE/main" "$TMP" | grep -A2 '^changed in both' || echo "(no textual conflict rows)"
git branch -D "$TMP" >/dev/null
echo "(temp ref $TMP deleted)"
