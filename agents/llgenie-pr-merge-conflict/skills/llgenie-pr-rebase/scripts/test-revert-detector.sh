#!/usr/bin/env bash
# Negative control for the "-X theirs silent revert" detector inside post-rebase-verify.sh.
#
# Asserts EXIT STATUS, not message text: a test that greps the wording passes on a harmless
# rephrase while the logic is broken. Runs in a throwaway repo so the detector's precondition
# ("base is an ancestor of HEAD") genuinely holds -- on this lane's real branch it does not,
# because the branch is behind main, so the check is skipped by design there.
#
# Three cases, in the order the semantics were learned:
#   1. SUBSTITUTION   base's line replaced by a different one  -> rc=1 (FAIL)
#      The shape that actually bit: `ci_images.py latest agent` -> `ref agent`.
#   2. PURE DELETION  a line removed, nothing added            -> rc=0 (NOTE, not a failure)
#      A branch may legitimately delete an obsolete line. Failing here rejects correct work,
#      which this lane's rules forbid a check from doing (measured: a synthetic intentional
#      deletion was first reported as a revert).
#   3. RESTORED       the base's wording put back              -> rc=0
set -uo pipefail

HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
VERIFY="$HERE/post-rebase-verify.sh"
[ -f "$VERIFY" ] || { echo "cannot find post-rebase-verify.sh beside this test" >&2; exit 2; }

T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
cd "$T" || exit 2
git init -q .
git config user.email t@t.example
git config user.name t

printf 'run the tool with latest agent\n' > recipe.mk
printf 'alpha\nobsolete\n' > notes.txt
git add -A && git commit -qm base
BASE=$(git rev-parse HEAD)   # every case is measured against THIS, not HEAD~1

# --- case 1: SUBSTITUTION (the real -X theirs shape) -----------------------
printf 'run the tool with ref agent\n' > recipe.mk
git add -A && git commit -qm 'case1 substitution'
bash "$VERIFY" "$BASE" >/tmp/rev_c1.$$ 2>&1
rc_c1=$?

# --- case 2: PURE DELETION (legitimate removal) ----------------------------
printf 'run the tool with latest agent\n' > recipe.mk
printf 'alpha\n' > notes.txt
git add -A && git commit -qm 'case2 pure deletion'
bash "$VERIFY" "$BASE" >/tmp/rev_c2.$$ 2>&1
rc_c2=$?

# --- case 3: RESTORED ------------------------------------------------------
printf 'alpha\nobsolete\n' > notes.txt
git add -A && git commit -qm 'case3 restored'
bash "$VERIFY" "$BASE" >/tmp/rev_c3.$$ 2>&1
rc_c3=$?

# --- case 4: the AUTHORSHIP assertion must be wired and able to fail ---------
# A stub that always reports a bad author: if post-rebase-verify prints SAFE TO PUSH anyway, the
# assertion is decorative. This is the wiring test for assertion 12 specifically.
mkdir -p scripts
printf 'import sys\nprint("bad author trailer")\nsys.exit(1)\n' > scripts/check_pr_authors.py
printf 'alpha\nobsolete\n' > notes.txt
git add -A && git commit -qm 'case4 authorship'
bash "$VERIFY" "$BASE" >/tmp/rev_c4.$$ 2>&1
rc_c4=$?
rm -rf scripts

# --- case 5: BEHIND the base must NOT fail (#1015) --------------------------
# main advancing under a mergeable PR is legitimate; a gate that reds here pushes a reader into a
# rebase the owner's rule says not to do. Built with a divergent branch that is strictly behind.
git checkout -q "$BASE" 2>/dev/null
printf 'forward\n' > ahead.txt && git add -A && git commit -qm 'case5 base advances'
AHEAD=$(git rev-parse HEAD)
git checkout -q -B behind "$BASE" 2>/dev/null
bash "$VERIFY" "$AHEAD" >/tmp/rev_c5.$$ 2>&1
rc_c5=$?
# --- case 6: a base never fetched (unknown sha) must FAIL -------------------
bash "$VERIFY" "0000000000000000000000000000000000000000" >/tmp/rev_c6.$$ 2>&1
rc_c6=$?

# --- case 7: DIVERGENT but merging cleanly must NOT fail (the real PR state) --
# Neither tip is an ancestor of the other; main advanced and the branch carries its own commits.
# This is the ordinary state #1015 blesses, and it must not read as DO NOT PUSH.
git checkout -q -B diverge "$BASE" 2>/dev/null
printf 'branchwork\n' > branch.txt && git add -A && git commit -qm 'case7 branch commit'
git checkout -q - 2>/dev/null
bash "$VERIFY" "$AHEAD" >/tmp/rev_c7.$$ 2>&1
rc_c7=$?

echo "  case1 SUBSTITUTION:  verify rc=$rc_c1  (want 1)"
echo "  case2 pure deletion: verify rc=$rc_c2  (want 0 — NOTE, not failure)"
echo "  case3 restored:      verify rc=$rc_c3  (want 0)"
echo "  case4 authorship:    verify rc=$rc_c4  (want 1 — a stub bad-author check must red it)"
echo "  case5 behind base:   verify rc=$rc_c5  (want 0 — #1015 blesses behind-but-mergeable)"
echo "  case6 unknown base:  verify rc=$rc_c6  (want 1 — a base never fetched cannot be verified)"
echo "  case7 divergent+clean: verify rc=$rc_c7 (want 0 — the ordinary PR state, #1015)"
grep -E 'base lines replaced|base lines deleted|no base lines lost' /tmp/rev_c1.$$ | sed 's/^/    c1: /'
grep -E 'base lines replaced|base lines deleted|no base lines lost' /tmp/rev_c2.$$ | sed 's/^/    c2: /'
grep -E 'base lines replaced|base lines deleted|no base lines lost' /tmp/rev_c3.$$ | sed 's/^/    c3: /'
rm -f /tmp/rev_c1.$$ /tmp/rev_c2.$$ /tmp/rev_c3.$$

fail=0
[ "$rc_c1" -eq 0 ] && { echo "FAIL: missed a SUBSTITUTION that reverted a base line" >&2; fail=1; }
[ "$rc_c2" -ne 0 ] && { echo "FAIL: rejected a legitimate pure deletion" >&2; fail=1; }
[ "$rc_c3" -ne 0 ] && { echo "FAIL: false-positive on a restored tree" >&2; fail=1; }
[ "$rc_c4" -eq 0 ] && { echo "FAIL: a failing check_pr_authors did not stop the push (assertion 12 is decorative)" >&2; fail=1; }
[ "$rc_c5" -ne 0 ] && { echo "FAIL: rejected a branch that is merely BEHIND the base (#1015 allows it)" >&2; fail=1; }
[ "$rc_c6" -eq 0 ] && { echo "FAIL: accepted a base sha that was never fetched" >&2; fail=1; }
[ "$rc_c7" -ne 0 ] && { echo "FAIL: rejected a divergent branch that merges cleanly (the ordinary PR state)" >&2; fail=1; }
[ "$fail" -eq 0 ] || exit 1
echo "PASS: catches the substitution revert, allows a deliberate deletion, clears a restored tree,"
echo "      a bad-author check reds the push; behind and divergent-but-clean are NOTEs,"
echo "      and only a real conflict or an unfetched base reds the push"
