#!/usr/bin/env bash
# One batch, one cause: rebase each branch onto the freshly fetched main, regenerate the index from
# fragments, verify notes==rows, run the two modules that were red, and push with a lease.
# Never edits a row into a diff — `make changes-index` is the only writer of CHANGES.md.
set -u
# Resolve the checkout rather than pinning one host path: this script ships to every clone and to
# CI, where the repository lives at a different absolute path. $LLGENIE_REPO wins, else walk up
# from this script's own directory to the .git root, else cwd.
if [ -n "${LLGENIE_REPO:-}" ]; then
  P="$LLGENIE_REPO"
else
  _d=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd); P=""
  while [ "$_d" != "/" ]; do
    [ -e "$_d/.git" ] && { P="$_d"; break; }
    _d=$(dirname -- "$_d")
  done
  [ -n "$P" ] || P="$(pwd)"
fi
cd "$P" || exit 1
MAIN=$(git rev-parse origin/main)

for spec in "$@"; do
  N=${spec%%:*}; REST=${spec#*:}; REMOTE=${REST%%:*}; BR=${REST#*:}
  WT="$P/../llgenie-wt/b$N"
  echo "=== #$N $REMOTE/$BR ==="
  git worktree remove --force "$WT" 2>/dev/null
  git worktree prune >/dev/null 2>&1
  git fetch "$REMOTE" "$BR:refs/remotes/$REMOTE/$BR" --quiet || { echo "  fetch failed"; continue; }
  BEFORE=$(git rev-parse --short "$REMOTE/$BR")
  if git merge-base --is-ancestor "$REMOTE/$BR" origin/main; then echo "  no-op (already an ancestor of main)"; continue; fi
  git worktree add -B "b$N" "$WT" "refs/remotes/$REMOTE/$BR" --force >/dev/null 2>&1 || { echo "  worktree failed"; continue; }
  cd "$WT" || continue
  # CHANGES.md is generated and conflicts on every rebase (main + branch both added rows). Resolve it by
  # taking main's table wholesale and continuing; the final make changes-index regenerates from fragments,
  # so no row is lost or hand-merged.
  if ! GIT_EDITOR=true git rebase origin/main >/tmp/rb-$N.log 2>&1; then
    CONF=$(git diff --name-only --diff-filter=U)
    CONFLIST=$(echo "$CONF" | sed '/^$/d' | sort -u)
    ONLY_CHANGES=1
    for f in $CONFLIST; do [ "$f" = "CHANGES.md" ] || ONLY_CHANGES=0; done
    if [ "$ONLY_CHANGES" = 1 ] && [ -n "$CONFLIST" ]; then
      git checkout origin/main -- CHANGES.md && git add CHANGES.md
      if ! GIT_EDITOR=true git rebase --continue >/tmp/rb-$N.log 2>&1; then
        echo "  continue conflict: $(git diff --name-only --diff-filter=U | tr '\n' ' ')"
        git rebase --abort 2>/dev/null; cd "$P"; continue
      fi
      echo "  (CHANGES.md resolved via main's table + regenerate)"
    else
      echo "  REBASE CONFLICT (files: $CONFLIST)"
      git rebase --abort 2>/dev/null; cd "$P"; continue
    fi
  fi
  make changes-index >/dev/null 2>&1
  if [ -n "$(git status --porcelain)" ]; then
    git add -A
    git -c user.name='Andy Holst' -c user.email='andy.holst@protonmail.com' commit -q --amend --no-edit
  fi
  NOTES=$(git ls-tree -r --name-only HEAD agent-wiki/ | grep -c '\.md$')
  ROWS=$(git show HEAD:CHANGES.md | grep -cE '^\| [0-9]{4}-[0-9]{2}-[0-9]{2} \|')
  echo "  rebased $BEFORE -> $(git rev-parse --short HEAD) · notes=$NOTES rows=$ROWS"
  if [ "$NOTES" != "$ROWS" ]; then echo "  ACCEPTANCE FAILED (notes != rows) — not pushing"; cd "$P"; continue; fi
  ROOT=$(pwd)
  if timeout 400 docker run --rm -u root -v "$ROOT":/repo:rw -v "$P":"$P":rw -w /repo llgenie/test \
      python -m pytest tests/test_changes_index.py tests/test_check_docs.py -p no:cacheprovider -q >/tmp/t-$N.log 2>&1; then
    echo "  gates: $(tail -1 /tmp/t-$N.log)"
  else
    echo "  GATES FAILED: $(grep -E '^FAILED' /tmp/t-$N.log | head -2 | tr '\n' ' ')"; cd "$P"; continue
  fi
  LEASE=$(git rev-parse "$REMOTE/$BR")
  if git push --force-with-lease="refs/heads/$BR:$LEASE" "$REMOTE" "HEAD:refs/heads/$BR" >/tmp/p-$N.log 2>&1; then
    echo "  pushed $(git rev-parse --short HEAD) (was $BEFORE) to $REMOTE"
  else
    echo "  PUSH REFUSED: $(tail -1 /tmp/p-$N.log)"
  fi
  cd "$P"
done
