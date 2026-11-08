# ci-verdict-unjudged-red-blocker

## MODIFIED Requirements

### Requirement: The unjudged-red set is exactly the merger's block set

`scripts/ci_verdict.py::UNJUDGED_RED_CONCLUSIONS` must be exactly `auto_merge.RED_CONCLUSIONS`
(`{failure, timed_out, startup_failure, cancelled, neutral}`), pinned equal by
`tests/test_ci_verdict.py::test_the_blocking_conclusions_are_the_merger_s_rule`. A `cancelled`/`neutral`
unjudged row IS a red: `auto_merge` refuses a merge on both (#1250 Finding B), so a verdict that ignored
them would call a head clean the merger refuses (the #2116/#2237 contract).

#### Scenario: a cancelled unjudged row from a workflow the verdict did not judge blocks

Given a head carrying a `cancelled` check-run (e.g. `engine-build-pr-trigger`) from a workflow the
verdict did not judge, beside the judged `CI` rows,
When `unjudged_reds` reads that head,
Then it returns that row, named with its workflow, conclusion and run id — the verdict cannot post
`success` at a head `auto_merge` refuses.
- **Test:** `tests/test_ci_verdict.py::test_a_cancelled_unjudged_row_from_another_workflow_blocks`

#### Scenario: a neutral unjudged row likewise blocks

Given a head carrying a `neutral` check-run from an unjudged workflow,
When `unjudged_reds` reads that head,
Then it returns that row — `neutral` is as much a red as `cancelled`.
- **Test:** `tests/test_ci_verdict.py::test_a_cancelled_unjudged_row_from_another_workflow_blocks`
  (the same assertion covers both via `TRANSIENT_CONCLUSIONS`)

#### Scenario: auto-merge's own merge=cancelled sweep at a main push is still a transient

Given a `merge` row (conclusion `cancelled`, resolving to the `auto-merge` workflow FILE) at a `main`
push head, beside a green judged `CI`,
When `unjudged_reds` reads that head,
Then it returns no row for that `merge` row — auto-merge's OWN sweep is excluded by FILE
(`TRANSIENT_FILES`), never by the conclusion class.
- **Test:** `tests/test_ci_verdict.py::test_auto_merges_own_cancelled_row_is_a_transient_not_a_blocker`
  (renamed from `test_a_cancelled_unjudged_row_is_a_transient_not_a_blocker`)

#### Scenario: a genuine failure from an unjudged workflow still blocks

Given a `failure` row from any unjudged workflow (auto-merge included),
When `unjudged_reds` reads that head,
Then it names that row — the transient exemption is per FILE and so narrow it cannot weaken #2116.
- **Test:** `tests/test_ci_verdict.py::test_a_failure_from_an_unjudged_workflow_still_blocks`

#### Scenario: the pin catches a drift to a subset

Given `UNJUDGED_RED_CONCLUSIONS` shrunk to a strict subset of `auto_merge.RED_CONCLUSIONS` (the #2231
shape) while the tests are unchanged,
When `test_the_blocking_conclusions_are_the_merger_s_rule` runs,
Then it reds on the `UNJUDGED_RED_CONCLUSIONS == auto_merge.RED_CONCLUSIONS` assertion and names the
missing `cancelled`/`neutral` — the pin that would have caught #2231.
- **Proven:** sabotage run (revert the fix, keep the new tests) reported
  `FAILED test_a_cancelled_unjudged_row_from_another_workflow_blocks` and
  `FAILED test_the_blocking_conclusions_are_the_merger_s_rule`; restore reported `54 passed`.
