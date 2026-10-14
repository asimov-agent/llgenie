# wiring-guard

## ADDED Requirements

### Requirement: every test and script is wired to a make target

A tracked document (`tests/test_*.py`, `scripts/*.py`) MUST be reachable from a make
target or a workflow step, directly or transitively (a target names it; a script that runs
or imports it is itself wired; a makefile calls the target). A document wired to nothing
MUST be an error that names it and says how to wire it — a test file in the tree that no
gate runs reads as coverage while proving nothing.

WHEN a new test or script is added and no target, chain or workflow step reaches it
THEN `make check-wiring` fails, naming the document.

#### Scenario: the real tree is fully wired and each host-only decision is dated

- **Given** the real checkout, its makefiles and its workflows
- **When** the wiring is checked
- **Then** no document is unwired, no recorded decision is stale, and every document is either reached by the CI workflows or recorded in `tests/fixtures/host-only-wiring.json`
- **And** every recorded decision names a reason, the target a human runs and the date
- **Test:** `tests/test_wiring.py::test_the_real_tree_has_no_unwired_document`

#### Scenario: a new test file no target names fails, and naming it is the fix

- **Given** a checkout whose `test-unit` target names only `tests/test_a.py`
- **When** the wiring is checked
- **Then** it exits non-zero and names `tests/test_b.py` as wired to nothing
- **And** adding `tests/test_b.py` to the target the CI job runs makes the check pass
- **Test:** `tests/test_wiring.py::test_a_new_test_file_no_target_names_fails_and_naming_it_fixes_it`

#### Scenario: the report says how each document is wired

- **Given** the real checkout and its recorded decisions
- **When** the report is rendered (`make wiring-report`)
- **Then** it counts the documents that run in CI, lists every host-only decision with the target a human runs, and reports no unwired or CI-unreached document
- **Test:** `tests/test_wiring.py::test_the_report_names_every_document_and_the_host_only_decisions`

### Requirement: a check CI cannot run is a dated decision, and it must not rot

A document reached only by targets the CI workflows never call MUST be recorded in
`tests/fixtures/host-only-wiring.json` with a `reason`, the `target` a human runs and a
`decided` date. A recorded entry that CI starts reaching, or whose file is gone, MUST be an
error — the record cannot rot. A malformed entry (no reason) MUST fail loudly.

WHEN a test runs only on hardware a CI runner does not have
THEN the omission is a recorded decision, and it is deleted the moment CI would run it.

#### Scenario: a host-only target needs a decision, and the decision goes stale

- **Given** a test named only by a target no workflow calls
- **When** the wiring is checked
- **Then** it fails, naming the host-only situation and the decisions file
- **And** a reasoned, dated decision for it makes the check pass
- **And** once a workflow runs that target, the decision is reported as stale and must be deleted
- **And** a decision missing its reason is refused
- **Test:** `tests/test_wiring.py::test_a_target_ci_never_runs_needs_a_dated_decision_and_goes_stale`

### Requirement: a workflow that calls a missing make target fails

Every `make <target>` in a workflow `run:` block MUST name a target that exists. A typo is
a silent no-op in `run:`, so it MUST be an error.

WHEN a workflow calls a target the Makefile does not define
THEN the check exits non-zero and names the workflow and the target.

#### Scenario: a workflow typo names no such target

- **Given** a workflow whose step runs `make ci-unti`
- **When** the wiring is checked
- **Then** it exits non-zero and names the file and the missing target
- **Test:** `tests/test_wiring.py::test_a_workflow_that_calls_a_missing_make_target_fails`

### Requirement: the guard runs in the pipeline it guards

`make check-wiring` MUST be a step of `ci-unit` (the regular PR pipeline) and
`tests/test_wiring.py` MUST be named by `make test-unit`, so the guard itself cannot
become dead code — the failure mode it exists to catch.

WHEN the Makefile is read
THEN `ci-unit` runs the wiring check and the unit target names the guard test.

#### Scenario: the guard is wired to ci-unit and to the unit target

- **Given** the Makefile
- **When** the `ci-unit` job and the `test-unit` target are read
- **Then** `$(MAKE) check-wiring` is in `ci-unit`, `tests/test_wiring.py` is in `test-unit`, and both targets exist
- **Test:** `tests/test_wiring.py::test_the_guard_runs_in_ci_unit_and_this_file_runs_in_test_unit`
