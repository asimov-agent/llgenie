# A merged PR must close an issue whose own acceptance criteria are checked (issue #1792)

`closes #<n>` proves a PR body NAMES an issue — it does not prove the issue's own definition of
done (issue #745: "a criterion a reviewer cannot tick is not one") was met. The repository's only
acceptance write-back, `acceptance_writeback.py` (issue #1644), is deliberately verdict-gated: an
auto-merged PR with no reviewer verdict tick nothing, so a #491-class merge can close an issue that
sits 5/5 `- [ ]` and the close verifies green — nothing reads the criteria the PR claimed to satisfy.

## What changed

`scripts/check_pr_acceptance.py` is a merge-time verification gate, the acceptance-side sibling of
`check-pr-closing`. It reuses the gate surfaces CI already mounts — `check_pr_closing.closing_references`
(the linked-issue set), `issue_body.section_body` + `acceptance_writeback.CHECKBOX_RE` (the
`## Acceptance criteria` checkbox parse) — imported, never restated. A new `make check-pr-acceptance`
target and a step beside `check-pr-closing` in `ci.yml` and `scope.yml` run it with the LIVE PR body
(read via `gh api`, issue #1589) and the LIVE linked issue at merge time.

The gate reports, it never ticks:

- **claim-unchecked** — a criterion in the closed issue's `## Acceptance criteria` is still `- [ ]`
  and the PR body does not name it out of scope under `## Not covered` with a linked work item;
- **claim-exceeds** — the PR body's own `- [x]` names a criterion the linked issue still has
  unchecked.

Verification only: the write-back stays #1644's verdict-driven seam; this gate surfaces the
discrepancy so a lane/tool intended to prove the criteria can, and a merge that closes an un-proven
issue does not verify silently green. Deliberately green for an issue with no criteria, no linked
issue, or a non-`#N` close — nothing is held that the issue did not declare.
