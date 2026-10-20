# unit-suite-aggregator

## ADDED Requirements

### Requirement: the hermetic unit suite is discovered, never enumerated

`make test-unit` MUST NOT name its test files by hand. The suite MUST be computed by
`scripts/unit_tests.py` from `tests/test_*.py`, so a new test file is in the gate the moment it
exists and two changes that add tests never edit the same line. A `tests/test_*.py` the
aggregator does not select MUST be a dated exclusion recorded in
`tests/fixtures/unit-suite.json` with its reason, its issue and the target that runs it instead.

WHEN a new `tests/test_*.py` is added and the Makefile is not touched
THEN it is part of `make test-unit` and the gate runs it.

#### Scenario: a new test file joins the unit suite with no Makefile edit

- **Given** a checkout whose tree holds a `tests/test_new.py` and a Makefile whose unit target runs the aggregator
- **When** the aggregator's selection is computed
- **Then** `tests/test_new.py` is selected and the Makefile names no test file at all
- **And** the pytest invocation the aggregator builds carries that file
- **Test:** `tests/test_unit_suite.py::test_a_new_test_file_is_selected_without_a_makefile_edit`

#### Scenario: the real tree is fully accounted for

- **Given** the real checkout
- **When** every `tests/test_*.py` is compared against the aggregator's selection and the roster
- **Then** each file is either selected (and so runs in `make test-unit`) or recorded as an exclusion with a reason, an issue, a date and the target that runs it
- **And** the roster's consistency check reports no finding
- **Test:** `tests/test_unit_suite.py::test_every_test_file_in_the_real_tree_is_in_the_suite_or_recorded`

#### Scenario: the report names the selection and the exclusions

- **Given** the real checkout
- **When** the aggregator lists its selection and its exclusions
- **Then** it prints the selected paths and, for each exclusion, the target that runs it instead
- **Test:** `tests/test_unit_suite.py::test_the_cli_lists_the_selection_and_the_exclusions`

### Requirement: an exclusion from the unit suite is a dated decision, and it must not rot

An entry in `tests/fixtures/unit-suite.json` MUST carry `reason`, `issue`, `decided` and the
`target` that runs the file instead. An entry whose file is gone, missing a field, naming a
target that does not exist, naming a target whose recipe does not name the file, or a
`deselect` entry whose test no longer exists MUST be an error that names the finding — an
exclusion cannot shrink the gate silently, and it cannot claim a runner that does not run it.

WHEN the roster records a file as not hermetic
THEN the record names why, when, by which issue, and the target that runs it — and it goes stale
loudly when any of that stops being true.

#### Scenario: an exclusion whose file is gone or whose fields are missing fails

- **Given** a roster with an entry for a file that does not exist, and an entry missing its reason
- **When** the roster consistency is checked
- **Then** it exits non-zero and names the stale entry and the missing field
- **Test:** `tests/test_unit_suite.py::test_a_stale_or_malformed_exclusion_fails_loudly`

#### Scenario: an exclusion cannot claim a runner that does not run it

- **Given** a roster entry naming a target that does not exist in the Makefile
- **When** the roster consistency is checked
- **Then** it exits non-zero and names the target
- **And** an entry whose target exists but whose recipe does not name the file fails the same way
- **Test:** `tests/test_unit_suite.py::test_an_exclusion_naming_a_target_that_does_not_run_it_fails`

#### Scenario: a deselection whose test is gone fails, and `run` refuses to start

- **Given** a roster deselecting a node id no test in that file defines
- **When** the roster consistency is checked
- **Then** it exits non-zero and names the node id
- **And** `run` exits non-zero before pytest executes when the roster is inconsistent, so the gate cannot start from a broken roster
- **Test:** `tests/test_unit_suite.py::test_a_deselection_of_a_gone_test_fails_and_run_refuses_to_start`

### Requirement: the suite is deselected by node id, never by a `-k` substring

The aggregator MUST pass `--deselect <file>::<test>`, exactly the node ids the roster records,
and MUST NOT use a `-k` expression: `-k` matches substrings, so a new test whose name contains a
deselected test's name would be silently dropped from the gate.

WHEN the aggregator builds the pytest invocation
THEN every deselected test is passed as an exact node id and no `-k` argument is present.

#### Scenario: the invocation carries exact node ids

- **Given** the real roster's deselections
- **When** the invocation is built
- **Then** each one appears as `--deselect tests/test_<file>.py::<test>` and `-k` appears nowhere
- **Test:** `tests/test_unit_suite.py::test_the_invocation_deselects_by_node_id_and_never_by_k`

### Requirement: the wiring guard sees the discovery seam

`make check-wiring` MUST treat a `tests/test_*.py` the aggregator selects as wired by the target
that runs the aggregator, and MUST report the roster's consistency findings, so a file excluded
from the unit suite still has to be reached by a target CI runs or be a recorded decision.

WHEN a test file is in the aggregator's selection but no target names it
THEN the wiring guard reports it wired through the discovery target, not as unwired.

#### Scenario: a discovered test is wired through the aggregator

- **Given** a checkout whose unit target runs `scripts/unit_tests.py run` and whose `tests/` holds a file the aggregator selects
- **When** the wiring graph is built
- **Then** that file is reachable through `make test-unit` and the check passes
- **And** removing the aggregator call from the recipe leaves it wired to nothing again
- **Test:** `tests/test_wiring.py::test_a_discovered_test_file_is_wired_through_the_aggregator`

#### Scenario: the real tree stays green with the seam in place

- **Given** the real checkout
- **When** `make check-wiring` runs
- **Then** no document is unwired, the roster reports no finding, and every exclusion is reached by a target CI runs or is a recorded host-only decision
- **Test:** `tests/test_wiring.py::test_the_real_tree_has_no_unwired_document`
