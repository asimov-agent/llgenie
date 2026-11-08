# manual-only-red-reaction

## MODIFIED Requirements

### Requirement: A red PR is no longer an automatic issue/repair source

`run-failure-reactor.yml` and `fix-bot.yml` must be MANUAL-ONLY: each may start only on
`workflow_dispatch`. A re-added `workflow_run` / `schedule` / other non-dispatch trigger in either file
must make `make check-workflows` FAIL.

#### Scenario: the reactor starts only on a human dispatch

Given a `run-failure-reactor.yml` whose `on:` block carries only `workflow_dispatch` (with a `run_id`
input), and no `workflow_run` or `schedule`,
When `make check-workflows` (the `check-manual-only` rule) reads it,
Then it reports no manual-only violation.
- **Gate:** `scripts/check_workflows.py::check_manual_only`; `tests/test_workflows_valid.py::
  test_a_manual_only_workflow_with_no_extra_trigger_is_accepted`

#### Scenario: re-adding `workflow_run` to either manual-only file is a violation

Given a manual-only file whose `on:` block carries `workflow_run` (or `schedule`) beside
`workflow_dispatch`,
When `make check-workflows` reads it,
Then it reports a `workflow-manual-only` violation naming the trigger, and `make check-workflows` exits
non-zero.
- **Gate:** `scripts/check_workflows.py::check_manual_only`; `tests/test_workflows_valid.py::
  test_a_manual_only_workflow_regaining_schedule_is_a_violation` and
  `test_a_manual_only_workflow_regaining_workflow_run_is_a_violation`
- **Negative control (measured):** re-adding `schedule: "17 * * * *"` to `fix-bot.yml` makes
  `make check-workflows` fail with `re-gained a non-dispatch trigger: schedule` (rc=1); restoring the
  dispatch-only file clears it (rc=0). Same for a `workflow_run` trigger.

#### Scenario: the reactor's dropped roster leaves a dated, reasoned exemption

Given the reactor's `workflow_run` roster is removed (so those workflows' reds are no longer
auto-routed),
When `check_workflow_run_coverage` reads the tree,
Then every such workflow is either covered by a remaining roster (CI / ci-scope / ci-requeue) or has a
dated entry with a `reason` in `tests/fixtures/workflow-run-exemptions.json`, and the gate reports no
`workflow-run-uncovered` violation.
- **Gate:** `scripts/check_workflows.py::check_workflow_run_coverage`
