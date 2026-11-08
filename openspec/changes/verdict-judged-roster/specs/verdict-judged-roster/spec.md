# verdict judged roster

## ADDED Requirements

### Requirement: The verdict NAMES a blocking check-run it did not judge

`scripts/ci_verdict.py` judges the jobs of ONE finished `CI` run against its published scope decision.
`scripts/auto_merge.py` refuses a merge on ANY blocking check-run at the head (`failure`, `timed_out`,
`startup_failure`, `cancelled`, `neutral` — issue #1386). So the verdict must also read the head's
other check-runs and, when one of them blocks the merge and belongs to a workflow the verdict does not
judge, it must not post a plain `success`: the posted check-run is `failure` and names that check, its
workflow and its run id.

The blocking set is exactly `scripts/auto_merge.RED_CONCLUSIONS`, so the verdict can never call a head
clean that the merger will refuse.

#### Scenario: a green judged run beside an unjudged red is not posted as success

Given a finished `CI` run at head `aeac049f` whose jobs are all green (`verdict=green success=10 failure=0`)
and a check-run `trigger` with `conclusion=failure` from the `engine-build-pr-trigger` workflow
(Actions run `42440650801`),
When `make ci-verdict RUN_ID=42440650781 HEAD_SHA=aeac049f… CHECK_RUN_OUT=<file>` runs,
Then it exits 1 and the payload carries `conclusion=failure`,
And the output names `check 'trigger' … workflow='engine-build-pr-trigger…' run=42440650801`.
- **Test:** `tests/test_ci_verdict.py::test_the_1982_specimen_names_the_unjudged_red_and_its_run_id`
- **Test:** `tests/test_ci_verdict.py::test_green_ci_beside_an_unjudged_red_is_not_posted_as_success`

#### Scenario: the same head with that check green is a clean verdict again

Given the identical head and judged run, with the sibling check-run's conclusion `success`,
When the verdict runs,
Then it exits 0 and posts `conclusion=success` — no unjudged red is named.
- **Test:** `tests/test_ci_verdict.py::test_the_same_head_with_that_check_green_returns_to_a_clean_verdict`

#### Scenario: the judged workflow's own reds and the verdict's own row are not unjudged

Given check-runs from `CI` (the judged workflow) and a `ci-verdict` row (the verdict's own posted
answer),
When `unjudged_reds()` runs,
Then neither is reported — the judged run's rows are the decision table's business, and the
`ci-verdict` row is the answer being posted.
- **Test:** `tests/test_ci_verdict.py::test_a_judged_workflows_red_and_the_verdicts_own_row_are_not_unjudged`

#### Scenario: a red from a non-Actions app is named, never dropped

Given a blocking check-run whose `details_url` carries no Actions run id,
When `unjudged_reds()` runs,
Then the row is returned under its app (`<app: …>`) with an empty run id — an unresolvable red fails
closed.
- **Test:** `tests/test_ci_verdict.py::test_a_check_run_from_another_app_is_named_not_dropped`

#### Scenario: the verdict's blocking set is the merger's rule

Given the verdict's `BLOCKING_CONCLUSIONS` and the merger's `RED_CONCLUSIONS`,
When they are compared,
Then they are equal, so the verdict cannot call a head clean that `auto_merge.py` refuses.
- **Test:** `tests/test_ci_verdict.py::test_the_blocking_conclusions_are_the_merger_s_rule`

### Requirement: The poster population and the judged set are held as a SUBSET check

`make verdict-roster` prints every workflow that can post a check-run at a PR head (a
`pull_request`/`pull_request_target` trigger), the set `ci-verdict.yml` judges, the difference, and the
findings. The comparison is `judged <= posters` — never equality, because the workflow set grows by
design. Every poster carries a dated judgement decision in `data/verdict-roster.json`; an entry that
names no poster is reported STALE, so the roster cannot rot in either direction.

#### Scenario: the shipped tree is green and the difference is the three unjudged posters

Given the repository tree,
When `scripts/verdict_roster.py check` runs,
Then it exits 0 with no findings, and the difference is exactly `engine-build-pr-trigger.yml`,
`holds.yml` and `scope.yml`.
- **Test:** `tests/test_verdict_roster.py::test_the_shipped_tree_carries_a_decision_for_every_poster_and_judges_a_subset`

#### Scenario: a new pull_request workflow with no decision reds the gate

Given a tree whose `pull_request` population has grown by one workflow with no entry in
`data/verdict-roster.json`,
When `make check-workflows` reads that tree,
Then it exits 1 with `verdict-roster-unrecorded/<file>` — and the same tree with a dated decision is
green (a subset check, not an equality).
- **Test:** `tests/test_verdict_roster.py::test_a_new_pull_request_workflow_with_no_decision_reds_the_gate`
- **Test:** `tests/test_verdict_roster.py::test_a_new_pull_request_workflow_with_a_decision_keeps_the_gate_green`

#### Scenario: a decision that lies, is undated, or is stale is a finding

Given a decision claiming `judged: true` while `ci-verdict.yml` does not list the workflow, or an
exemption with no reason/date/issue, or an entry naming a workflow that no longer posts at a PR head,
When the roster reads it,
Then each is a finding (`verdict-roster-not-judged`, `verdict-roster-undated`,
`verdict-roster-stale`).
- **Test:** `tests/test_verdict_roster.py::test_a_decision_that_claims_judged_but_is_absent_from_the_roster_reds`
- **Test:** `tests/test_verdict_roster.py::test_an_undated_exemption_is_a_finding`
- **Test:** `tests/test_verdict_roster.py::test_a_stale_decision_is_reported_not_ignored`

### Requirement: A CI run with no head to read cannot claim a clean verdict

A live judgment (`RUN_ID`) or an explicit `--checks` file reads the head's check-runs. A missing head
sha is refused (exit 2, no check-run) rather than assumed clean; a pure `--jobs` replay says on the
record that the head was not read.

#### Scenario: a run with no head sha is refused

Given `--run-id` with no head sha and no `--head-sha`,
When the verdict runs,
Then it exits 2 with `no head sha … an unreadable head is not a clean head` and posts nothing.
- **Test:** `tests/test_ci_verdict.py::test_the_cli_refuses_to_invent_a_verdict_without_input`
