# engine-build-dispatch

## ADDED Requirements

### Requirement: a dispatched sweep builds every engine at its pin, outside the main pipeline

The repository MUST provide a `workflow_dispatch`-only workflow that builds and verifies every
engine × variant in the committed params, and MUST NOT be triggered by `pull_request`, `push` or a
schedule. Its matrix MUST come from `make engine-build-matrix` (the real `matrix()` over
`containers/engines/params/*.json`), never from a hand-written roster, and every row MUST be built
with `make build-engine` and then verified with `make test-engine-stage` in that row's own mode.

WHEN a maintainer dispatches the sweep
THEN one job per engine × variant builds from the committed params and verifies the image, and no
other pipeline grows a full-sweep job.

#### Scenario: the workflow is dispatch-only

- **Given** `.github/workflows/engine-build.yml`
- **When** its trigger block is read
- **Then** `workflow_dispatch` is the only trigger — no `pull_request`, `push`, `schedule` or `cron`
- **Test:** `tests/test_engine_build_workflow.py::test_it_is_dispatch_only_and_never_runs_on_a_pr_push_or_schedule`

#### Scenario: the guard runs first and the contract is stated

- **Given** the workflow text
- **When** its header and job order are read
- **Then** `# Trigger surface:`, `# Flow:` and `# Never:` are present and `guard` is the first job
- **Test:** `tests/test_engine_build_workflow.py::test_it_has_the_guard_before_any_secret_and_documents_itself`

#### Scenario: the matrix comes from the committed params

- **Given** the workflow's matrix job and the `engine-build-matrix` target
- **When** both are read and the target is run
- **Then** the job calls `make -s engine-build-matrix` with the dispatch inputs, and the target
  emits 20+ rows from `matrix()`
- **Test:** `tests/test_engine_build_workflow.py::test_the_matrix_comes_from_the_committed_params_not_a_roster`

#### Scenario: every row is built and then verified

- **Given** the build job
- **When** its steps are read
- **Then** each row runs `make build-engine` and `make test-engine-stage … TEST=${{ matrix.test }}`,
  fans out with `max-parallel`, and skips the `none` placeholder
- **Test:** `tests/test_engine_build_workflow.py::test_every_row_is_built_and_then_verified`

#### Scenario: publishing is opt-in

- **Given** the dispatch inputs and the publish wiring
- **When** the default and the step guard are read
- **Then** `push` defaults to `false` and the publish path is gated on `inputs.push == 'true'`
- **Test:** `tests/test_engine_build_workflow.py::test_it_publishes_only_when_the_dispatch_asks_for_it`

### Requirement: an image is published only after its binary answered

The sweep MUST build a row without publishing, verify it, and only then publish when the dispatch
asked for it — `make push-engine` is its own step, gated on `push=true`, and re-checks the binary's
flags before pushing. A build step that publishes is a defect: a failing binary would reach GHCR.

WHEN a row is dispatched with `push=true`
THEN the order is build → verify → push, and a failed verification stops before the push.

#### Scenario: the order is build, verify, publish

- **Given** the workflow's build job
- **When** its steps are read
- **Then** `run: make build-engine`, `run: make test-engine-stage` and `run: make push-engine`
  appear in that order, the build carries no `PUSH=`, and the push step is gated on `inputs.push`
- **Test:** `tests/test_engine_build_workflow.py::test_every_row_is_built_and_then_verified` and `::test_it_publishes_only_when_the_dispatch_asks_for_it`

### Requirement: the make target is the one list, and it is documented

`make engine-build-matrix` MUST print the JSON matrix from `scripts/engine_image.py matrix`,
supporting `ENGINE=` and `ARCH=` filters, MUST be declared in `.PHONY`, carry a `make help` line and
be documented in `README.md`; the workflow MUST appear in the generated dispatch-forms table.

WHEN the targets and the README are checked
THEN the new target is documented and the dispatch table carries the new workflow row.

#### Scenario: the target and the docs are wired

- **Given** the Makefile and README
- **When** `make check-docs` and `make check-dispatch-forms` run
- **Then** both pass, naming `engine-build-matrix` and `engine-build.yml`
- **Test:** `tests/test_engine_build_workflow.py::test_the_matrix_comes_from_the_committed_params_not_a_roster` (target runs from the real tree) plus `make check-docs` / `make check-dispatch-forms` in `ci-unit`
