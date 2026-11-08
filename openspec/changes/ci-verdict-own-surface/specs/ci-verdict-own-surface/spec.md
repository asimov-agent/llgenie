# ci verdict own surface

## ADDED Requirements

### Requirement: The verdict never counts its own workflow surface as an unjudged red

`scripts/ci_verdict.py::unjudged_reds` must not return a row from the verdict's own workflow
(`OUR_WORKFLOW_FILE = ci-verdict.yml`), neither the posted `CHECK_NAME` row nor the `judge`/`guard`
JOB auto-rows, resolved by workflow FILE (not by row name). A `workflow_run` posts those job rows at the
default-branch head every run, so counting them reds a green `main` head on the verdict's own footprint.

#### Scenario: a failed judge row of this workflow is not an unjudged red

Given a head carrying a `judge` row (conclusion `failure`) whose `details_url` resolves to the
`ci-verdict` workflow file, plus the judged `CI` rows,
When `unjudged_reds` reads that head,
Then it returns no row for that `judge` row — the verdict's own footprint never blocks the verdict.
- **Test:** `tests/test_ci_verdict.py::test_the_verdicts_own_judge_rows_are_not_unjudged_reds`

### Requirement: A cancelled or neutral unjudged row is a transient, never a block

`unjudged_reds` must block only on a genuinely-red unjudged conclusion
(`UNJUDGED_RED_CONCLUSIONS = {failure, timed_out, startup_failure}`). A `cancelled`/`neutral` unjudged
row is a superseded / owed-nothing transient (the same reason this verdict posts `neutral` for a
superseded head) and never reds a green judged head. `BLOCKING_CONCLUSIONS` (the merger's #1386 rule,
pinned equal to `auto_merge.RED_CONCLUSIONS` by `test_the_blocking_conclusions_are_the_merger_s_rule`)
is unchanged.

#### Scenario: auto-merge's merge=cancelled row does not red the head

Given a `merge` row (conclusion `cancelled`) resolving to the `auto-merge` workflow at a `main` push
head, beside a green judged `CI`,
When `unjudged_reds` reads that head,
Then it returns no row for that `merge` row — a cancelled sweep is a transient.
- **Test:** `tests/test_ci_verdict.py::test_a_cancelled_unjudged_row_is_a_transient_not_a_blocker`

#### Scenario: a genuine failure from an unjudged workflow still blocks

Given a `failure` row from any unjudged workflow (auto-merge included),
When `unjudged_reds` reads that head,
Then it names that row — the transient exemption is narrow and does not weaken #2116.
- **Test:** `tests/test_ci_verdict.py::test_a_failure_from_an_unjudged_workflow_still_blocks`

### Requirement: A failure conclusion is never titled green

The posted check-run title names the EFFECTIVE verdict the conclusion carries: a `conclusion=failure`
row is titled `ci-verdict: red`, never `ci-verdict: green`. `ci_scope.check_run_payload` accepts an
optional `title` override; `ci_verdict.main()` computes it from the posted conclusion.

#### Scenario: green judged run forced red by unjudged blockers posts title red

Given a green judged run beside an unjudged red,
When the verdict posts the check-run,
Then the row concludes `failure` and is titled `ci-verdict: red` — the title never says green on a
failure row.
- **Test:** `tests/test_ci_verdict.py::test_a_failure_conclusion_is_never_titled_green` and the title
  assertions in `test_green_ci_beside_an_unjudged_red_is_not_posted_as_success`

#### Scenario: the #2221 specimen head reaches a success verdict

Given the finished `CI` run `42460411318` at head `07a7db2a` whose head carries the verdict's own
`judge` rows and auto-merge's `merge=cancelled`,
When `make ci-verdict RUN_ID=42460411318 HEAD_SHA=07a7db2a… CHECK_RUN_OUT=<file>` runs at the fixed
head,
Then it holds the run to its decision (`verdict=green success=10 failure=0`), excludes the own-surface
and transient rows, and writes `conclusion=success`, rc 0.
- **Verification:** the branch-head reproduction recorded in
  `agent-wiki/2026-11-08-ci-verdict-own-surface-2221.md`
