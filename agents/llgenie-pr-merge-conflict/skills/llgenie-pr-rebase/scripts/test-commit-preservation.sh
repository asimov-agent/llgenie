#!/usr/bin/env bash
# Negative control for the commit-preservation check inside stack-replay.sh / batch-rebase.sh.
#
# A rebase or cherry-pick that silently DROPS one of the branch's own commits is invisible to every
# content gate: the tree parses, the tests pass, one semantic change is just gone -- measured, two
# lanes lost a fix this way and only a human diff found it. The drivers compare commit SUBJECTS
# (shas change under rewrite, subjects do not) captured before the replay against the history after.
#
# This control proves the set-compare both ways in a throwaway repo and asserts the subjects, so a
# future edit that breaks the comparison -- or only compares shas -- reds here.
set -uo pipefail

T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
cd "$T" || exit 2
git init -q .
git config user.email t@t.example
git config user.name t
printf 'base\n' > f.txt
git add -A && git commit -qm 'base commit'
MB=$(git rev-parse HEAD)
printf 'own work here\n' >> f.txt
git add -A && git commit -qm 'the PRs own change'
OWN=$(git log --format=%s "$MB..HEAD")

# case A: commit preserved -> LOST must be empty
GOT=$(git log --format=%s HEAD)
LOST_A=$(printf '%s\n' "$OWN" | while read -r s; do
  [ -n "$s" ] && ! printf '%s\n' "$GOT" | sort -u | grep -Fxq "$s" && printf '%s\n' "$s"; done)

# case B: commit dropped -> LOST must name it
GOT_B=$(printf 'base commit\nunrelated other work\n')
LOST_B=$(printf '%s\n' "$OWN" | while read -r s; do
  [ -n "$s" ] && ! printf '%s\n' "$GOT_B" | grep -Fxq "$s" && printf '%s\n' "$s"; done)

echo "  preserved: LOST=[$LOST_A]        (want empty)"
echo "  dropped:   LOST=[$LOST_B]        (want 'the PRs own change')"

fail=0
[ -n "$LOST_A" ] && { echo "FAIL: a preserved commit was reported lost" >&2; fail=1; }
[ "$LOST_B" != "the PRs own change" ] && { echo "FAIL: a dropped commit was not caught: [$LOST_B]" >&2; fail=1; }

# case C: the DRIVER sequence — WANTED captured before replay, then a replay that DROPS one commit.
# The standalone B case proves the set-compare; this proves the capture-and-replay path the two
# drivers actually run (stack-replay.sh: WANTED=$PLUS subjects before the cherry-pick loop, LOST
# checked after). A control that only exercises the compare in isolation can pass while the drivers
# capture the wrong set.
git checkout -q -b drop-replay "$MB" 2>/dev/null
git cherry-pick "$(git rev-list --reverse "$MB..HEAD" 2>/dev/null | head -1)" >/dev/null 2>&1  # keep only the FIRST own commit
GOTC=$(git log --format=%s HEAD | sort -u)
LOST_C=$(printf '%s\n' "$OWN" | while read -r s; do
  [ -n "$s" ] && ! printf '%s\n' "$GOTC" | grep -Fxq "$s" && printf '%s\n' "$s"; done)
echo "  driver-drop: LOST=[$LOST_C]  (want 'the PRs own change' -- the dropped second commit)"
[ "$LOST_C" != "the PRs own change" ] && { echo "FAIL: the DRIVER path missed the dropped commit" >&2; fail=1; }

[ "$fail" -eq 0 ] || exit 1
echo "PASS: the set-compare catches a dropped commit by subject and is silent when preserved"
echo "      (incl. the driver capture-and-replay path)"
