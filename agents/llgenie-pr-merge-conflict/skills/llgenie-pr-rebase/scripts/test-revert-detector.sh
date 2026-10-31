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

echo "  case1 SUBSTITUTION:  verify rc=$rc_c1  (want 1)"
echo "  case2 pure deletion: verify rc=$rc_c2  (want 0 — NOTE, not failure)"
echo "  case3 restored:      verify rc=$rc_c3  (want 0)"
echo "  case4 authorship:    verify rc=$rc_c4  (want 1 — a stub bad-author check must red it)"
grep -E 'base lines replaced|base lines deleted|no base lines lost' /tmp/rev_c1.$$ | sed 's/^/    c1: /'
grep -E 'base lines replaced|base lines deleted|no base lines lost' /tmp/rev_c2.$$ | sed 's/^/    c2: /'
grep -E 'base lines replaced|base lines deleted|no base lines lost' /tmp/rev_c3.$$ | sed 's/^/    c3: /'
rm -f /tmp/rev_c1.$$ /tmp/rev_c2.$$ /tmp/rev_c3.$$

fail=0
[ "$rc_c1" -eq 0 ] && { echo "FAIL: missed a SUBSTITUTION that reverted a base line" >&2; fail=1; }
[ "$rc_c2" -ne 0 ] && { echo "FAIL: rejected a legitimate pure deletion" >&2; fail=1; }
[ "$rc_c3" -ne 0 ] && { echo "FAIL: false-positive on a restored tree" >&2; fail=1; }
[ "$rc_c4" -eq 0 ] && { echo "FAIL: a failing check_pr_authors did not stop the push (assertion 12 is decorative)" >&2; fail=1; }
[ "$fail" -eq 0 ] || exit 1
echo "PASS: catches the substitution revert, allows a deliberate deletion, clears a restored tree,"
echo "      and a bad-author check reds the push"
