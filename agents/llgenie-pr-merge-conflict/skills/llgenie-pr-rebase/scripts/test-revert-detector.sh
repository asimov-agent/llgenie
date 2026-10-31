#!/usr/bin/env bash
# Negative control for the "-X theirs silent revert" detector inside post-rebase-verify.sh.
#
# Asserts EXIT STATUS, not message text: a test that greps the wording passes on a harmless
# rephrase while the logic is broken. Run in a throwaway repo so the detector's precondition
# ("base is an ancestor of HEAD") genuinely holds -- on this lane's real branch it does not,
# because the branch is behind main, so the check is skipped by design there.
#
# Three cases, because the FIRST draft of this control only covered one of them:
#   1. pure deletion      base line removed, unrelated file added     -> verify MUST exit 1
#   2. MODIFICATION       base line changed back to an older value   -> verify MUST exit 1
#      (this is the shape that actually bit: `ci_images.py latest agent` -> `ref agent`,
#       which is a one-line change, not a deletion, and case 1 alone did not cover it)
#   3. restored           the base line put back                     -> verify MUST exit 0
set -uo pipefail

HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
VERIFY="$HERE/post-rebase-verify.sh"
[ -f "$VERIFY" ] || { echo "cannot find post-rebase-verify.sh beside this test" >&2; exit 2; }

T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
cd "$T" || exit 2
git init -q .
git config user.email t@t.example
git config user.name t

printf 'line-one\nkeep-me\n' > file.txt
printf 'run the tool with latest\n' > recipe.mk
git add -A && git commit -qm base
BASE=$(git rev-parse HEAD)   # the real base; every case is measured against THIS, not HEAD~1

# --- case 1: pure deletion -------------------------------------------------
printf 'line-one\n' > file.txt
printf 'new\n' > added.txt
git add -A && git commit -qm 'case1 delete'
bash "$VERIFY" "$BASE" >/tmp/rev_c1.$$ 2>&1
rc_c1=$?

# --- case 2: MODIFICATION back to an older value ---------------------------
# restore case 1, then change the base's line to an older spelling + add an unrelated file,
# which is precisely what a strategy-flag resolution leaves behind.
printf 'line-one\nkeep-me\n' > file.txt
printf 'run the tool with ref\n' > recipe.mk
printf 'new\n' > added.txt
git add -A && git commit -qm 'case2 modify'
bash "$VERIFY" "$BASE" >/tmp/rev_c2.$$ 2>&1
rc_c2=$?

# --- case 3: restored ------------------------------------------------------
printf 'run the tool with latest\n' > recipe.mk
git add -A && git commit -qm 'case3 restored'
bash "$VERIFY" "$BASE" >/tmp/rev_c3.$$ 2>&1
rc_c3=$?

echo "  case1 pure deletion:  verify rc=$rc_c1  (want 1)"
echo "  case2 MODIFICATION:   verify rc=$rc_c2  (want 1)"
echo "  case3 restored:       verify rc=$rc_c3  (want 0)"
grep -E 'drops base lines|pure deletions' /tmp/rev_c1.$$ | sed 's/^/    c1: /'
grep -E 'drops base lines|pure deletions' /tmp/rev_c2.$$ | sed 's/^/    c2: /'
grep -E 'drops base lines|pure deletions' /tmp/rev_c3.$$ | sed 's/^/    c3: /'
rm -f /tmp/rev_c1.$$ /tmp/rev_c2.$$ /tmp/rev_c3.$$

fail=0
[ "$rc_c1" -eq 0 ] && { echo "FAIL: missed a pure deletion of a base line" >&2; fail=1; }
[ "$rc_c2" -eq 0 ] && { echo "FAIL: missed a MODIFICATION that reverted a base line" >&2; fail=1; }
[ "$rc_c3" -ne 0 ] && { echo "FAIL: false-positive on a restored tree" >&2; fail=1; }
[ "$fail" -eq 0 ] || exit 1
echo "PASS: detector catches a deletion AND a reverted modification, and clears a restored tree"
