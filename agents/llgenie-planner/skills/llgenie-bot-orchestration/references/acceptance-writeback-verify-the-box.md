# Verify the acceptance checkbox, not the reviewer's comment

A reviewer lane's `acceptance_writeback --proven …` can post its correction
comment yet FAIL to flip the item's box on the issue body. The witness comment
exists on the wire; the `- [ ]` stays blank.

When a reviewer reports "I re-ticked AC<n> → N/5":

- Do NOT accept the count from the comment or the DM. The comment existing is
  not the checkbox changing.
- Read the live acceptance section of the ISSUE body:
  `gh api repos/<org>/<repo>/issues/<n> --jq .body` → count the `- [x]` vs
  `- [ ]` lines and read the trailing `unproven:` block (it still lists any item
  whose write-back did not land).
- Only the box states are evidence. Quote the live count back on the issue.

Also: an ACC criterion that names SPECIFIC files is satisfied only by those
files. A differently-dated artifact documenting the same resolved state is a
DIFFERENT artifact — it does not satisfy the criterion's wording, even if its
substance overlaps. Substitution judgments are the reviewer's call only if they
formally override the wording; otherwise the criterion binds to whatever change
(the rebase/merge) actually brings the named files onto the head.
