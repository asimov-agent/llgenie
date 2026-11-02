# auto-merge APPROVED review body now carries a citable verdict: run id + head sha (issue #1619)

The #1273/`check-pr-closing`-class standard a reviewer enforces is that a verdict names the run id
AND the head sha it judged, so a reader or auditor can re-fetch the evidence from the record alone.
A board-sweep measured on 2026-11-02 (issue #1619) found a whole class of merged PRs whose only
declaring verdict was the auto-merge `APPROVED` review body — and that body was generic text (`LGTM`,
or "Approved by the repo's auto-merge job (issue #491): the run is green and the only thing missing
was a required review"). Five PRs merged that week (#1210, #1247, #1259, #1294, #1555) carried no
re-fetchable (run id, head sha) pair in their comments ∪ reviews.

`scripts/auto_merge.py::approve()` is the one place that posts that body. The fix mirrors the rule-14
merge announcement (`announce_merge`): the approval body now interpolates

- **the head sha being judged**: `state["headRefOid"]`, threaded through `try_approve()` into `approve()`
  (a PR whose state carries no head sha is never approved — an approval that cannot say which tree it
  judged is the same defect as a merge with no comment);
- **the run id deciding it**: `$GITHUB_RUN_ID` (the running CI run, exactly as the merge announcement
  uses it; a local `make auto-merge` invocation honestly says so rather than inventing a run id).

So the declaring verdict on every auto-merged PR now satisfies the #1273 sweep regexes
(`\b\d{11,}\b` for the run, `\b[0-9a-f]{7,40}\b` for the head sha) that the reviewer-lane verdict
comments already satisfy (13/13 of the reviewer's own terminal verdicts were citable before this
change; the gap was specifically the auto-merge APPROVAL body). It does not weaken any gate, does not
change who approves or merges, and does not alter the merge decision — only what the approval says on
the way out (issue #1088 stands: this lane posts the PR, the owner's fleet identity/auto-merge still
executes the merge).
