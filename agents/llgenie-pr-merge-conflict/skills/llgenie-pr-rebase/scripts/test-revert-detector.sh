#!/usr/bin/env bash
# Negative control for the "-X theirs silent revert" detector inside post-rebase-verify.sh.
#
# Asserts EXIT STATUS, not message text: a test that greps the wording passes on a harmless
# rephrase while the logic is broken. Runs in throwaway repos so the detector's precondition
# ("base is an ancestor of HEAD") genuinely holds -- on this lane's real branch it does not,
# because the branch is behind main, so the check is skipped by design there.
#
# The detector (check 11, fixed by #2099) distinguishes a REVERT from an EDIT by comparing the
# base lines HEAD lost AGAINST the branch's OWN diff -- the lines the branch deleted from the
# fork point where it diverged (read via ORIG_HEAD, set by `git rebase`):
#
#   1. CORRECT EDIT   a branch's own intended substitution, clean rebase -> rc=0 (NOTE)
#      The gone base lines ARE the branch's own deletions, so they are explained.
#   2. -X THEIRS      a real `-X theirs` rebase reverting a base line the branch never touched
#                     -> rc=1 (FAIL). This is the shape the detector exists to catch.
#   3. PURE DELETION  a line removed with nothing added, clean rebase -> rc=0 (NOTE, not failure)
#      A branch may legitimately delete an obsolete line.
#
# Cases 4-7 keep the wiring and non-rebase guarantees that do not involve the discriminator.
set -uo pipefail

HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
VERIFY="$HERE/post-rebase-verify.sh"
[ -f "$VERIFY" ] || { echo "cannot find post-rebase-verify.sh beside this test" >&2; exit 2; }

# Each case runs in its OWN throwaway repo, because ORIG_HEAD is a single ref: a rebase in one
# case would otherwise leak its pre-rebase tip into the next and flip that case's verdict.
case_repo() {
  T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
  cd "$T" || exit 2
  git init -q .
  git config user.email t@t.example
  git config user.name t
}

# --- case 1: CORRECT EDIT, a real clean rebase carrying the branch's own substitution --------
# base has build(); branch rewrites build(); main advances an UNRELATED file; clean rebase keeps
# the branch's intended edit. Every gone base line is the branch's own deletion -> rc=0.
case_repo
printf 'def build():\n    poll()\n    emit()\n' > engine.py
printf 'alpha\n' > notes.txt
git add -A && git commit -qm base
git checkout -q -b work 2>/dev/null
printf 'def build():\n    return verdict(poll(), emit())\n' > engine.py   # branch's intended edit
git add -A && git commit -qm 'branch rewrites build()'
WORK_ORIG=$(git rev-parse HEAD)
git checkout -q master
printf 'alpha\nmain\n' > notes.txt                                        # main advances notes.txt
git add -A && git commit -qm 'main advances notes'
MAIN=$(git rev-parse HEAD)
git checkout -q work 2>/dev/null
GIT_EDITOR=true git rebase "$MAIN" >/dev/null 2>&1                       # clean rebase
HEAD1=$(git rev-parse HEAD)
bash "$VERIFY" "$MAIN" >/tmp/rvd_c1.$$ 2>&1 ; rc_c1=$?

# --- case 2: -X THEIRS revert, a real strategy-flag rebase ------------------------------------
# old origin O has 'ref agent'; main advances to 'latest agent'; branch carries stale 'ref agent'
# and touches recipe.mk; `-X theirs` resolves the hunk to the branch's stale side, dropping main's
# 'latest agent' -- a line the branch's own diff never deleted -> rc=1 (FAIL).
case_repo
printf 'run the tool with ref agent\n' > recipe.mk                       # old origin
git add -A && git commit -qm O
git checkout -q -b work 2>/dev/null
printf '# comment\nrun the tool with ref agent\n' > recipe.mk            # branch carries stale ref
git add -A && git commit -qm 'branch touches recipe.mk carrying stale ref'
git checkout -q master
printf 'run the tool with latest agent\n' > recipe.mk                    # main advances ref->latest
git add -A && git commit -qm 'main advances to latest'
MAIN2=$(git rev-parse HEAD)
git checkout -q work 2>/dev/null
GIT_EDITOR=true git rebase -X theirs "$MAIN2" >/dev/null 2>&1            # the revert shape
bash "$VERIFY" "$MAIN2" >/tmp/rvd_c2.$$ 2>&1 ; rc_c2=$?

# --- case 3: PURE DELETION, a line removed with nothing added ---------------------------------
# A branch may legitimately delete an obsolete line. Its own diff deleted it, so the loss is
# explained -> rc=0 (NOTE), not a failure. (Regression: was first reported as a revert.)
case_repo
printf 'alpha\nobsolete\n' > notes.txt
printf 'x\n' > a.txt
git add -A && git commit -qm base
git checkout -q -b work 2>/dev/null
printf 'alpha\n' > notes.txt                                             # delete the obsolete line
git add -A && git commit -qm 'branch deletes obsolete line'
git checkout -q master
printf 'x\nmain\n' > a.txt
git add -A && git commit -qm 'main advances a.txt'
MAIN3=$(git rev-parse HEAD)
git checkout -q work 2>/dev/null
GIT_EDITOR=true git rebase "$MAIN3" >/dev/null 2>&1
bash "$VERIFY" "$MAIN3" >/tmp/rvd_c3.$$ 2>&1 ; rc_c3=$?

# --- case 4: the AUTHORSHIP assertion must be wired and able to fail ---------------------------
# A stub that always reports a bad author: if post-rebase-verify prints SAFE TO PUSH anyway, the
# assertion is decorative. This is the wiring test for assertion 12 specifically. (No rebase, so
# ORIG_HEAD is unset and case 11 falls back to NOTE -- the FAIL here is check 12 alone.)
case_repo
printf 'run the tool with latest agent\n' > recipe.mk
printf 'alpha\nobsolete\n' > notes.txt
git add -A && git commit -qm base
BASE=$(git rev-parse HEAD)   # every case is measured against THIS, not HEAD~1
mkdir -p scripts
printf 'import sys\nprint("bad author trailer")\nsys.exit(1)\n' > scripts/check_pr_authors.py
printf 'alpha\nobsolete\n' > notes.txt
git add -A && git commit -qm 'case4 authorship'
bash "$VERIFY" "$BASE" >/tmp/rvd_c4.$$ 2>&1 ; rc_c4=$?

# --- case 5: BEHIND the base must NOT fail (#1015) ---------------------------------------------
# main advancing under a mergeable PR is legitimate; a gate that reds here pushes a reader into a
# rebase the owner's rule says not to do. Built with a divergent branch that is strictly behind.
case_repo
printf 'x\n' > base.txt ; git add -A && git commit -qm base
BASE=$(git rev-parse HEAD)
git checkout -q -b ahead 2>/dev/null
printf 'forward\n' > ahead.txt && git add -A && git commit -qm 'case5 base advances'
AHEAD=$(git rev-parse HEAD)
git checkout -q -B behind "$BASE" 2>/dev/null
bash "$VERIFY" "$AHEAD" >/tmp/rvd_c5.$$ 2>&1 ; rc_c5=$?

# --- case 6: a base never fetched (unknown sha) must FAIL ---------------------------------------
case_repo
printf 'x\n' > base.txt ; git add -A && git commit -qm base
bash "$VERIFY" "0000000000000000000000000000000000000000" >/tmp/rvd_c6.$$ 2>&1 ; rc_c6=$?

# --- case 7: DIVERGENT but merging cleanly must NOT fail (the real PR state) ------------------
# Neither tip is an ancestor of the other; main advanced and the branch carries its own commits.
# This is the ordinary state #1015 blesses, and it must not read as DO NOT PUSH.
case_repo
printf 'x\n' > base.txt ; git add -A && git commit -qm base
git checkout -q -b work 2>/dev/null
printf 'branchwork\n' > branch.txt && git add -A && git commit -qm 'case7 branch commit'
git checkout -q master
printf 'mainwork\n' > main.txt && git add -A && git commit -qm 'case7 main commit'
MAIN7=$(git rev-parse HEAD)
git checkout -q work 2>/dev/null
bash "$VERIFY" "$MAIN7" >/tmp/rvd_c7.$$ 2>&1 ; rc_c7=$?

echo "  case1 correct edit (clean): verify rc=$rc_c1  (want 0)"
echo "  case2 -X theirs revert:     verify rc=$rc_c2  (want 1)"
echo "  case3 pure deletion (clean): verify rc=$rc_c3 (want 0)"
echo "  case4 authorship:           verify rc=$rc_c4  (want 1 — a stub bad-author check must red it)"
echo "  case5 behind base:          verify rc=$rc_c5  (want 0 — #1015 blesses behind-but-mergeable)"
echo "  case6 unknown base:         verify rc=$rc_c6  (want 1 — a base never fetched cannot be verified)"
echo "  case7 divergent+clean:      verify rc=$rc_c7  (want 0 — the ordinary PR state, #1015)"
grep -E 'base lines|no base lines lost' /tmp/rvd_c1.$$ | sed 's/^/    c1: /'
grep -E 'base lines|no base lines lost' /tmp/rvd_c2.$$ | sed 's/^/    c2: /'
grep -E 'base lines|no base lines lost' /tmp/rvd_c3.$$ | sed 's/^/    c3: /'
rm -f /tmp/rvd_c1.$$ /tmp/rvd_c2.$$ /tmp/rvd_c3.$$ /tmp/rvd_c4.$$ /tmp/rvd_c5.$$ /tmp/rvd_c6.$$ /tmp/rvd_c7.$$

fail=0
[ "$rc_c1" -ne 0 ] && { echo "FAIL: rejected a branch's own intended substitution (check 11 over-fires)" >&2; fail=1; }
[ "$rc_c2" -eq 0 ] && { echo "FAIL: missed a real -X theirs revert of a base line" >&2; fail=1; }
[ "$rc_c3" -ne 0 ] && { echo "FAIL: rejected a legitimate pure deletion" >&2; fail=1; }
[ "$rc_c4" -eq 0 ] && { echo "FAIL: a failing check_pr_authors did not stop the push (assertion 12 is decorative)" >&2; fail=1; }
[ "$rc_c5" -ne 0 ] && { echo "FAIL: rejected a branch that is merely BEHIND the base (#1015 allows it)" >&2; fail=1; }
[ "$rc_c6" -eq 0 ] && { echo "FAIL: accepted a base sha that was never fetched" >&2; fail=1; }
[ "$rc_c7" -ne 0 ] && { echo "FAIL: rejected a divergent branch that merges cleanly (the ordinary PR state)" >&2; fail=1; }
[ "$fail" -eq 0 ] || exit 1
echo "PASS: a deliberate edit passes, a real -X theirs revert reds, a pure deletion passes,"
echo "      bad-author reds the push; behind and divergent-but-clean are NOTEs,"
echo "      and only a real revert, a conflict or an unfetched base reds the push"
