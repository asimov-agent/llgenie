# all-pipelines-sweep

## ADDED Requirements

### Requirement: the umbrella dispatches every dispatchable workflow, awaits each, and reports every disabled one

There is exactly one workflow, `.github/workflows/all-pipelines.yml`, triggered by `workflow_dispatch` and a
weekly `schedule` on its own odd minute, that dispatches every dispatchable workflow **except itself**, awaits
each dispatched run's verdict, and prints a table plus a summary. It never cancels or re-runs another lane's
run, and one red workflow does not abort the sweep — the full table is printed and the job fails at the end if
any non-disabled dispatched run is failed.

WHEN the umbrella runs
THEN it lists every dispatchable workflow except itself, dispatches each, waits for each run's conclusion, prints `workflow · dispatched run id · status/conclusion · completed_at` and a `N ok · M failed · K disabled` summary, and exits non-zero iff any non-disabled run failed.

#### Scenario: every dispatchable workflow is dispatched and awaited, except the umbrella itself

- **Given** a repo whose workflows include `arms.yml` (dispatchable, active) and `all-pipelines.yml` (itself)
- **When** the sweep dispatches and awaits
- **Then** `arms.yml` is dispatched and its run's `conclusion` and `completed_at` are awaited and recorded
- **And** `all-pipelines.yml` is excluded (dispatching every dispatchable workflow must not dispatch the umbrella or it recurses)
- **Test:** `tests/test_all_pipelines.py::test_the_umbrella_dispatches_every_dispatchable_except_itself_and_awaits`

#### Scenario: failure isolation — one red pipeline does not abort the sweep

- **Given** two dispatched workflows, one concluding `failure` and one `success`
- **When** the sweep finishes
- **Then** the table contains both rows and the exit code is non-zero (the job fails at the end, not mid-sweep)
- **Test:** `tests/test_all_pipelines.py::test_failure_isolation_emits_full_table_and_fails_at_end`

#### Scenario: the sweep states the sha it swept

- **Given** a tree at a specific head sha
- **When** the sweep runs
- **Then** its report names that sha, so a green is a fact about a tree, not a date
- **Test:** `tests/test_all_pipelines.py::test_the_sweep_states_the_sha_it_swept`

### Requirement: a disabled workflow is reported DISABLED and excluded from ok/failed, with the excluded list printed

A workflow whose live state is not `active` MUST appear in the table as `DISABLED (owner re-enable required)`,
must NOT count toward `ok` or `failed`, and MUST be listed in a printed excluded list. The failure mode this
prevents is a green summary hiding dead pipelines.

WHEN a swept workflow is disabled_manually
THEN it is rendered `DISABLED (owner re-enable required)`, counted in `K disabled`, left out of `ok`/`failed`, and named in the printed excluded list.

#### Scenario: the disabled list appears in the table and the summary counts it separately

- **Given** a sweep where `security-scan.yml` is disabled and `arms.yml` succeeds
- **When** the summary is rendered
- **Then** the table contains `security-scan.yml · DISABLED (owner re-enable required)`, the excluded list names `security-scan.yml`, and the summary reads `1 ok · 0 failed · 1 disabled`
- **Test:** `tests/test_all_pipelines.py::test_a_disabled_workflow_is_reported_and_excluded`

#### Scenario: every disabled workflow is reported, never silently skipped

- **Given** a tree with several disabled workflows and several active ones
- **When** the sweep renders its report
- **Then** the count of `DISABLED` rows equals the number of non-active workflows in the tree, and the excluded list length matches
- **Test:** `tests/test_all_pipelines.py::test_every_disabled_workflow_is_reported`

### Requirement: `make targets-coverage` lists every Makefile target with its callers, distinguishing internal from user-facing

`make targets-coverage` MUST print, for every Makefile target (from `make -qp`), the callers found — a workflow
step, a script reference, or none — and MUST mark `_`-prefixed targets as internal so a reader can tell which
user-facing targets no workflow/script runs.

WHEN `make targets-coverage` runs
THEN it prints every target, each marked internal (`_`-prefixed) or user-facing, with the callers found or `none`, and totals the set with no caller.

#### Scenario: every target is listed with a caller or `none`, and internal is distinct

- **Given** the real Makefile and its workflows/scripts
- **When** the targets-coverage report is rendered
- **Then** every `make -qp` target appears once, `_`-prefixed targets are marked internal, and a target that no workflow or script names appears with `callers: none`
- **Test:** `tests/test_targets_coverage.py::test_every_target_is_listed_with_a_caller_or_none`

#### Scenario: the report is reproducible and counts no-caller targets

- **Given** a make -qp projection of the Makefile
- **When** the report is rendered
- **Then** its totals (total targets, internal, no-caller) are stated and reproducible
- **Test:** `tests/test_targets_coverage.py::test_report_totals_are_stated_and_reproducible`

### Requirement: the umbrella and the coverage audit live behind the existing gates, and the disabled list is covered by a test

The new workflow MUST pass `check-workflows`, `ci-lint`, `check-wiring` and `check-dispatch-forms`; the new
scripts MUST be wired through make targets (`make check-wiring`); the dispatchable workflow MUST be listed in
the docs/BOTS.md `dispatch-forms` table; and at least one test MUST assert the umbrella's table includes the
disabled list.

WHEN the change is reviewed
THEN the workflow passes every guard, the dispatch table is regenerated, and the disabled-list behaviour is locked by a test in `make test-unit`.

#### Scenario: the disabled-list behaviour is locked by a test the gate runs

- **Given** the disabled-workflow classification logic
- **When** the test suite runs
- **Then** `tests/test_all_pipelines.py` fails if a disabled workflow is treated as `ok` or dropped from the excluded list
- **Test:** `tests/test_all_pipelines.py::test_a_disabled_workflow_is_reported_and_excluded`
