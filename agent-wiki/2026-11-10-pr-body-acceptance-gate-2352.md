# A PR whose own acceptance checklist is the SOLE vehicle merged with all four boxes unticked (issue #2352)

An engine-bump PR generates its OWN `## Acceptance criteria` checklist (the #1796 form gate demands one)
and closes no issue — nothing backs its acceptance. Measured 2026-11-09: PR #2267 merged via armed
auto-merge with all four PR-body boxes unticked, `ci-verdict` SUCCESS, no `check-pr-acceptance` row in
its status rollup, and at the merge head the published-pin criterion was FALSE (`[pins] NOT PUBLISHED
ghcr.io/asimov-agent/llgenie/llama-cpp:7d7f0287-2c544fb3-cpu (HTTP Error 404)`), the manifest appearing
only after the post-merge `engine-build push=true`. The same shape on #2263–#2268.

The #1644 write-back seam and the #1792 issue-side gate only cover the ISSUE-body write-back path; an
engine-bump PR's acceptance record lives in the PR BODY and was read by no gate.

## The gate

`make check-pr-acceptance-body` (`scripts/check_pr_acceptance.py body` + pure
`pr_body_acceptance_findings`) fires ONLY in the sole-vehicle scope — a PR body that carries its own
`## Acceptance criteria` checklist and closes no issue. In that scope:

- an unticked `- [ ]` box at the current head is `acceptance-body-unchecked` → RED;
- a `- [x]` tick that names no re-producible run id / command+rc+sha is `acceptance-body-tick-unprovable`
  → RED (the #1858 evidence rule, from the issue-side gate);
- a PR that closes an issue is left to the issue-side `check-pr-acceptance` (#1644/#1792), and a body
  with no checklist to `check-pr-acceptance-form` — neither is weakened.

It is VERIFICATION only; it ticks nothing. Both `ci.yml`'s `guard` job and `scope.yml`'s docs gate run
it beside `check-pr-acceptance` with the LIVE PR body (`gh api repos/<repo>/pulls/<n>`, issue #1589), so
a body-only fix clears on rerun; a push to main has no PR number and prints a `nothing to validate`
note instead of failing. The `guard` job is a row of the `ci_scope.JOBS` judged table, so a red box
reds the judged CI run → `ci-verdict` → auto-merge cannot arm.

## Proof

Tests drive the REAL script with the REAL #2267 bump payload (no mock of the decision):
`test_engine_bump_all_four_boxes_unticked_is_RED` (red on the original 4-unticked body),
`test_engine_bump_all_boxes_ticked_with_run_ids_is_GREEN`, `test_engine_bump_tick_with_no_evidence_is_RED`,
and `test_a_PR_that_closes_an_issue_is_skipped` (issue-body path untouched). The judged-set membership
is proven from the tree (`ci_scope.JOBS` contains `guard`; `verdict_roster.judged_files` includes
`ci.yml`) in `test_the_gate_step_is_in_the_judged_ci_guard_job`, not by grepping a string. Local run:
`52 passed` for `tests/test_pr_body_acceptance_gate.py + tests/test_check_pr_acceptance.py`.
