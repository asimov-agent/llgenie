# unit-suite-fast-group

## ADDED Requirements

### Requirement: a named subset a target runs is a group in the roster, never a hand-list

A make target MUST NOT name its test files by hand. When a target runs a SUBSET of the hermetic
unit suite rather than all of it, that subset MUST be recorded as a named group in
`tests/fixtures/unit-suite.json` — with its reason, its issue, its date and its files — and the
target MUST run `scripts/unit_tests.py run --group <name>`. So a new test that belongs to the
subset is added in the roster alone, and two changes that touch the subset never edit the same
recipe line.

WHEN a target runs a named group and the recipe names no test file
THEN the subset runs exactly the group's files and the roster is the only place they are named.

#### Scenario: `make test` runs the fast group and names no test file

- **Given** the real checkout and its `make test` target
- **When** the recipe and the fast group are read
- **Then** the recipe runs `run --group fast` and names no `tests/test_*.py`
- **And** the group's files are exactly the six the recipe used to name, and the invocation the group builds carries them
- **Test:** `tests/test_unit_suite.py::test_the_fast_group_is_recorded_and_make_test_names_no_file`

#### Scenario: the wiring guard attributes only the group to its target

- **Given** the real checkout, where `make test` runs the fast group and `make test-unit` runs the whole selection
- **When** the wiring graph is read
- **Then** `make test` is attributed exactly the group's files, not the whole ~20-minute selection
- **And** a file outside the group (e.g. `tests/test_wiring.py`) is attributed to `make test-unit` only
- **Test:** `tests/test_unit_suite.py::test_the_wiring_guard_attributes_only_the_fast_group_to_make_test`

### Requirement: a group is a dated decision and it must not rot

A group in `tests/fixtures/unit-suite.json` MUST carry `reason`, `issue`, `decided` and a non-empty
`files` list. A group that names no file, names a file that does not exist, names a file the roster
excludes from the hermetic suite, names the same file twice, or carries no reason/issue/date MUST be
an error that names the finding. An unknown group a recipe asks for MUST be fatal, so a target
cannot silently run nothing.

WHEN a group names a file that is gone or excluded, or the group itself is malformed
THEN the roster consistency check exits non-zero and names the group and the finding.

#### Scenario: a group naming a gone or excluded file fails

- **Given** a roster whose group names a file that does not exist, and one that names an excluded file
- **When** the roster consistency is checked
- **Then** it exits non-zero and names the group and the file
- **Test:** `tests/test_unit_suite.py::test_a_group_naming_a_gone_or_excluded_file_fails`

#### Scenario: a group with no file or no reason fails

- **Given** a group with an empty file list, and one with no reason
- **When** the roster consistency is checked
- **Then** it exits non-zero and names the missing file list or the missing reason
- **Test:** `tests/test_unit_suite.py::test_a_group_with_no_file_or_no_reason_fails`

#### Scenario: an unknown group is fatal

- **Given** a checkout whose recipe asks for a group the roster does not record
- **When** the group's files are computed and `run` is asked to start the gate
- **Then** both exit non-zero, naming the group, and pytest does not start
- **Test:** `tests/test_unit_suite.py::test_an_unknown_group_is_fatal`
