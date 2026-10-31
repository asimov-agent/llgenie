#!/usr/bin/env bash
# Replay a stacked PR's own commits onto the CURRENT tip of its stack base, then gate and push.
# `git rebase --onto` is wrong here: a stacked branch contains its base's commits, so replaying them
# re-conflicts. `git cherry <base> HEAD` names only the '+' commits, which are this PR's own work.
set -u
# Resolve the checkout and the resolver helper rather than pinning one host path: this script
# ships to every clone. $LLGENIE_REPO / $REBASE_RESOLVER win, else resolve from this script's
# own location, else cwd.
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
BASE_BRANCH=${STACK_BASE:-feat/agent-profile-implementer-skill}
# The resolver sits beside the other skill scripts; fall back to the historical profile path only
# if that file is absent, so an un-migrated host still works.
RESOLVER=${REBASE_RESOLVER:-$(dirname -- "${BASH_SOURCE[0]}")/resolve-fleet-triple.py}
[ -f "$RESOLVER" ] || RESOLVER=/home/asimov/.hermes/profiles/llgenie-pr-merge-conflict/cache/scratch/resolve-fleet-triple.py
cd "$P" || exit 1
git fetch origin "$BASE_BRANCH:refs/remotes/origin/$BASE_BRANCH" --quiet
BASE=refs/remotes/origin/$BASE_BRANCH

for spec in "$@"; do
  N=${spec%%:*}; BR=${spec#*:}
  # Never remove or prune a worktree: the owner-only commands delete a directory and cannot
  # see uncommitted work (issue #794). A unique per-run path makes removal unnecessary; the
  # leftovers are reported here and are the owner's to prune.
  STAMP=$(date +%Y%m%d-%H%M%S)-$$
  WT="$P/../llgenie-wt/s$N-$STAMP"
  echo "=== #$N $BR ==="
  git fetch origin "$BR:refs/remotes/origin/$BR" --quiet || { echo "  fetch failed"; continue; }
  BEFORE=$(git rev-parse --short "origin/$BR")
  PLUS=$(git cherry "$BASE" "origin/$BR" | grep '^+' | awk '{print $2}')
  if [ -z "$PLUS" ]; then echo "  no unique commits — already contained in the stack base"; continue; fi
  git worktree add -B "s$N-$STAMP" "$WT" "$BASE" >/dev/null 2>&1 || { echo "  worktree failed"; continue; }
  echo "  worktree: $WT (left in place — never removed by this script)"
  cd "$WT" || continue
  OK=1
  # Commit preservation: a cherry-pick that silently skips or drops one of this PR's own commits
  # (a rebase-resolution error) is invisible to every content gate — the tree parses, the tests
  # pass, one semantic change is just gone. Record the subjects of the commits we MEANT to replay
  # (the cherry-pick rewrites shas, so subjects are the stable identity), then assert after the
  # loop that each still exists in the replayed history. Measured: two lanes lost a fix to a
  # silent discard this way and only a human diff found it.
  WANTED=$(printf '%s\n' $PLUS | while read -r c; do git log -1 --format=%s "$c"; done)
  for c in $PLUS; do
    git cherry-pick "$c" >/dev/null 2>&1 && continue
    echo "  conflict at $(echo "$c" | cut -c1-8): $(git diff --name-only --diff-filter=U | tr '\n' ' ')"
    # CHANGES.md is generated: take the base's copy, then regenerate from docs/changes.d fragments
    for f in $(git diff --name-only --diff-filter=U); do
      case "$f" in
        CHANGES.md) git checkout "$BASE" -- "$f" 2>/dev/null ;;
      esac
    done
    python3 "$RESOLVER" . >/tmp/res-$N.log 2>&1
    # Anything the resolver did not union must NOT be resolved by picking a side: during a
    # cherry-pick `--ours` is the BASE side, so `git checkout --ours` silently DROPS the replayed
    # commit's own change -- a member of the exact silent-revert class this lane repairs. Measured
    # by reading this file: the fallback kept base lines for every conflicted file the resolver
    # could not judge, and the commit still proceeded. Refuse and abort instead; the author should
    # reconcile the two real intents, never inherit one silently.
    remaining=$(git diff --name-only --diff-filter=U)
    if [ -n "$remaining" ]; then
      echo "  unresolved conflict(s) the resolver did not union: $remaining"
      echo "  REFUSING to silently take a side (--ours would drop the replayed commit's own change)"
      OK=0; break
    fi
    git add -A
    if [ -n "$(git grep -l -E '^(<<<<<<<|>>>>>>>)' -- . 2>/dev/null)" ]; then echo "  MARKERS REMAIN — aborting"; OK=0; break; fi
    GIT_EDITOR=true git cherry-pick --continue >/dev/null 2>&1 || { echo "  continue failed — aborting"; OK=0; break; }
  done
  [ "$OK" = 0 ] && { git cherry-pick --abort 2>/dev/null; cd "$P"; continue; }
  # Verify no replayed commit was dropped: every subject we set out to replay must be in the new
  # history. `git log --format=%s` is order-insensitive set comparison, so a squashing or a skip
  # shows as a missing subject and refuses the push.
  GOT=$(git log --format=%s "$(git rev-parse --short HEAD)" 2>/dev/null | sort -u)
  LOST=$(printf '%s\n' "$WANTED" | while read -r s; do
    [ -n "$s" ] && ! printf '%s\n' "$GOT" | grep -Fxq "$s" && printf '%s\n' "$s"; done)
  if [ -n "$LOST" ]; then
    echo "  COMMIT LOST during replay — not pushing:"
    printf '      %s\n' "$LOST" | sed 's/^/    /'
    cd "$P"; continue
  fi
  make changes-index >/dev/null 2>&1
  if [ -n "$(git status --porcelain)" ]; then
    git add -A; git -c user.name='Andy Holst' -c user.email='andy.holst@protonmail.com' commit -q --amend --no-edit
  fi
  NOTES=$(git ls-tree -r --name-only HEAD agent-wiki/ | grep -c '\.md$')
  ROWS=$(git show HEAD:CHANGES.md | grep -cE '^\| [0-9]{4}-[0-9]{2}-[0-9]{2} \|')
  echo "  replayed $BEFORE -> $(git rev-parse --short HEAD) · notes=$NOTES rows=$ROWS"
  [ "$NOTES" != "$ROWS" ] && { echo "  NOTES!=ROWS — not pushing"; cd "$P"; continue; }
  ROOT=$(pwd)
  if timeout 400 docker run --rm -u root -v "$ROOT":/repo:rw -v "$P":"$P":rw -w /repo llgenie/test \
      python -m pytest tests/test_changes_index.py tests/test_check_docs.py -p no:cacheprovider -q >/tmp/st-$N.log 2>&1; then
    echo "  gates: $(tail -1 /tmp/st-$N.log)"
  else
    echo "  GATES FAILED: $(grep -E '^FAILED' /tmp/st-$N.log | head -2 | tr '\n' ' ')"; cd "$P"; continue
  fi
  LEASE=$(git rev-parse "origin/$BR")
  git push --force-with-lease="refs/heads/$BR:$LEASE" origin "HEAD:refs/heads/$BR" >/tmp/sp-$N.log 2>&1 \
    && echo "  pushed $(git rev-parse --short HEAD) (was $BEFORE)" \
    || echo "  PUSH REFUSED: $(tail -1 /tmp/sp-$N.log)"
  cd "$P"
done
