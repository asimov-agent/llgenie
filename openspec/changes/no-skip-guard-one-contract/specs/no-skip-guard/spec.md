# no-skip-guard

## ADDED Requirements

### Requirement: one written contract decides what a skip is

`tests/conftest.py` MUST state, in one paragraph above its hooks, what counts as a skip and which hook
owns which phase. A SKIP MUST be any report pytest marks `skipped`, in any phase and from any cause:
`pytest.skip()`, `@pytest.mark.skipif`, a conditional skip inside a test, or an `xfail` marker whose
test failed (pytest reports that as `skipped` with `wasxfail` set). An XFAIL MUST NOT be an exemption:
the repository has no "known failure" bucket in the hermetic gate, because a green gate means every
test ran and passed. `pytest_runtest_logreport` MUST own the call-phase verdict and
`pytest_report_teststatus` MUST own every phase, so a setup-, teardown- or module-level skip is caught
even though it produces no call-phase report.

#### Scenario: the contract is stated once, beside the hooks

- **Given** `tests/conftest.py`
- **When** a reader looks for the skip rule
- **Then** one paragraph above the hooks says what a skip is, that `xfail` is one, and which hook owns
  which phase — and no second copy of the rule exists elsewhere in the file
- **Test:** `tests/test_no_skip_guard.py::test_the_shared_predicate_is_the_one_decision`

### Requirement: both hooks ask one shared predicate

Every hook that fails a skip MUST ask `_skip_violation(report)`, the single predicate that decides what
a violation is. Neither hook may carry its own copy of the rule, and neither may add an `xfail`
exemption: an exemption introduced in ONE hook MUST red a test that names that hook.

#### Scenario: an xfail is a violation in each hook on its own

- **Given** a report exactly as pytest emits it for a test that failed behind `xfail` (`skipped=True`,
  `wasxfail` set, `when="call"`)
- **When** either `pytest_report_teststatus` or `pytest_runtest_logreport` sees it on its own
- **Then** that hook sets the report's outcome to `failed` and its message names the hook
- **Test:** `tests/test_no_skip_guard.py::test_each_hook_treats_an_xfail_as_a_skip_violation`

#### Scenario: a plain skip is a violation in each hook on its own

- **Given** a plain `pytest.skip()` report (`skipped=True`, no `wasxfail`)
- **When** either hook sees it on its own
- **Then** that hook sets the outcome to `failed`
- **Test:** `tests/test_no_skip_guard.py::test_each_hook_treats_a_plain_skip_as_a_violation`

#### Scenario: a passing report is left untouched

- **Given** a normal passing call-phase report
- **When** either hook sees it
- **Then** its outcome stays `passed` and no `longrepr` is attached
- **Test:** `tests/test_no_skip_guard.py::test_each_hook_leaves_a_passing_report_untouched`

#### Scenario: a setup-phase xfail is caught by the every-phase hook

- **Given** an `xfail` that failed during setup, which produces no call-phase report
- **When** `pytest_report_teststatus` sees it
- **Then** it is `failed` — the module-level case cannot slip past the call-phase hook
- **Test:** `tests/test_no_skip_guard.py::test_report_teststatus_owns_every_phase_so_a_setup_xfail_is_caught`

### Requirement: a recorded violation turns the process exit red

The guard MUST fail the RUN, not only the printed line: pytest computes its exit status from its own
failure counter, so a report mutation alone leaves a skipped test exiting 0. `pytest_sessionfinish`
MUST set the session's exit status to failed (1) when the run recorded at least one violation, and MUST
leave the status untouched when it recorded none.

#### Scenario: a recorded violation makes a green session red

- **Given** a session whose computed exit status is 0
- **And** a violation recorded by either hook
- **When** `pytest_sessionfinish` runs
- **Then** the session's exit status is 1
- **Test:** `tests/test_no_skip_guard.py::test_sessionfinish_turns_a_recorded_violation_into_a_red_exit`

#### Scenario: a clean run stays green

- **Given** a session whose computed exit status is 0 and an empty violation ledger
- **When** `pytest_sessionfinish` runs
- **Then** the exit status is unchanged
- **Test:** `tests/test_no_skip_guard.py::test_sessionfinish_leaves_a_clean_run_green`

### Requirement: a real run exits red for a skip or an xfail, and green for a clean file

Driven through pytest itself (the hooks wired the way pytest wires them), an `xfail`, a
`pytest.skip()` and a module-level `skipif` MUST each exit non-zero and name the offending test, while
a file of honestly passing tests MUST exit 0. The regression test MUST load the repository's own
`tests/conftest.py` by path; it MUST NOT restate the guard's logic.

#### Scenario: an xfail file exits red

- **Given** a pytest root whose conftest re-exports the repository's hooks
- **And** one test marked `@pytest.mark.xfail`
- **When** that file runs
- **Then** the process exits non-zero, names the test, and prints the no-skip message
- **Test:** `tests/test_no_skip_guard.py::test_a_real_skip_or_xfail_run_exits_red`

#### Scenario: a plain skip file exits red

- **Given** the same root and one test calling `pytest.skip()`
- **When** that file runs
- **Then** the process exits non-zero and names the test
- **Test:** `tests/test_no_skip_guard.py::test_a_real_skip_or_xfail_run_exits_red`

#### Scenario: a module-level skip exits red

- **Given** the same root and a module carrying `pytest.mark.skipif(True, …)`
- **When** that file runs
- **Then** the process exits non-zero and names the skipped test
- **Test:** `tests/test_no_skip_guard.py::test_a_real_skip_or_xfail_run_exits_red`

#### Scenario: a clean file exits green

- **Given** the same root and one honestly passing test
- **When** that file runs
- **Then** the process exits 0
- **Test:** `tests/test_no_skip_guard.py::test_a_clean_run_exits_green`

### Requirement: the tracked-defect pattern is documented where a lane looks

`docs/TESTING.md` (linked from `README.md`) MUST state that `xfail` is not available in this
repository and MUST name the replacement for a tracked defect — a test that asserts the defect's
CURRENT behaviour, so fixing the defect reds the test and its deletion is forced mechanically rather
than remembered.

#### Scenario: the testing doc states the xfail position and the replacement

- **Given** `docs/TESTING.md`
- **When** a lane looks for how to record a known defect
- **Then** it says `xfail` is a skip here and names the assert-the-defect pattern with its mechanical
  removal
- **Test:** `tests/test_no_skip_guard.py::test_the_testing_doc_states_the_xfail_position_and_the_replacement`
