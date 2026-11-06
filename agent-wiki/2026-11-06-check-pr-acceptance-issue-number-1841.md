# check-pr-acceptance failure output names the linked issue number (issue #1841)

`check-pr-acceptance` reds correctly on an issue whose acceptance criteria are unticked, but its
failure output did not tell the reader **which** issue was defective. Measured live on PR #1840
(closes #1791): a multi-issue PR's identical violation titles are indistinguishable in a CI log,
and the evidence printed the literal placeholder `closes #<n>` — a red that proves the failure but
not the fix, since a reader must re-run the `report` subcommand (or read the failing step's log) to
learn which issue to repair.

## What changed

`scripts/check_pr_acceptance.py` now threads the linked-issue number through the checking path:

- `acceptance_verdict(issue_body_text, pr_body)` → `acceptance_verdict(issue_body_text, pr_body, issue: int)`;
- `main()`'s `check` loop passes each `n` from `cpc.closing_references(body)` into the verdict;
- every finding's `where` is now `f"#{n}"` (was the static `"issue-criteria"` / `"pr-body-vs-issue"`),
  and the violation `title` names the issue (`closes the issue #{n}`), matching the `issue-unreadable`
  branch's shape;
- the literal `closes #<n>` placeholder in the evidence is replaced with the real `closes #{n}`.

`render()` is unchanged (it already prints each item's `title` and `evidence`); with `#N` in both, a
multi-issue PR's violations are distinguishable from a single CI log. The `report` subcommand still
names issues. New unit tests feed a 2-issue PR with one unticked criterion each and assert each
violation's evidence carries the correct `#N`, and that the literal placeholder no longer appears.