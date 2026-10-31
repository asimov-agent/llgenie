#!/usr/bin/env bash
# Negative control for the "-X theirs silent revert" detector inside post-rebase-verify.sh.
#
# Asserts EXIT STATUS, not message text: a test that greps the wording fails on a harmless
# rephrase and passes when the logic breaks. Run in a throwaway repo so the detector's
# precondition ("base is an ancestor of HEAD") genuinely holds -- on this lane's real branch it
# does not, because the branch is behind main, so the check is skipped by design there.
#
#   case 1  a commit deletes a base line (adding an unrelated file) -> verify MUST exit 1
#   case 2  the same tree with the base line restored              -> verify MUST exit 0
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
git add -A && git commit -qm base

# The reverting shape: a base line gone, an unrelated file added, nothing else.
printf 'line-one\n' > file.txt
printf 'new\n' > added.txt
git add -A && git commit -qm 'revert-ish'

bash "$VERIFY" HEAD~1 >/tmp/rev_bad.$$ 2>&1
rc_bad=$?

# The same tree with the base line restored.
printf 'line-one\nkeep-me\n' > file.txt
git add -A && git commit -qm restored
bash "$VERIFY" HEAD~2 >/tmp/rev_good.$$ 2>&1
rc_good=$?

echo "  reverting tree: verify rc=$rc_bad   (want 1)"
echo "  restored tree:  verify rc=$rc_good  (want 0)"
grep -E 'drops base lines|pure deletions' /tmp/rev_bad.$$ | sed 's/^/    /'
grep -E 'drops base lines|pure deletions' /tmp/rev_good.$$ | sed 's/^/    /'
rm -f /tmp/rev_bad.$$ /tmp/rev_good.$$

if [ "$rc_bad" -eq 0 ]; then
  echo "FAIL: the detector did not catch a base line deleted with nothing added" >&2
  exit 1
fi
if [ "$rc_good" -ne 0 ]; then
  echo "FAIL: the detector false-positives on a restored tree" >&2
  exit 1
fi
echo "PASS: detector catches the revert and clears the restored tree"
