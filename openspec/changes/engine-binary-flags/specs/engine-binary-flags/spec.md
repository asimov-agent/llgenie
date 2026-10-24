# engine-binary-flags

## ADDED Requirements

### Requirement: Every documented flag must answer, individually

The engine-file probe SHALL run EVERY flag the engine's manifest documents and SHALL report one
verdict per flag. A documented flag that exits non-zero, or prints nothing, SHALL fail the check and
SHALL be named in the failure together with its own output tail.

WHEN a built engine image's binary is probed
THEN each documented flag is executed separately and its own exit status and output are asserted.

#### Scenario: a binary that answers --version and not --help is a failure

Given a binary that prints a version for `--version` and exits 1 for `--help`
When  the documented flags `--version --help` are decided
Then  the check fails and the failure names `--help`.

- **Test:** `tests/test_engine_binary_flags.py::test_a_dead_help_flag_reds_naming_the_flag`

#### Scenario: a binary that answers everything passes

Given a binary that prints text and exits 0 for every flag
When  `--version --help` are decided
Then  the check passes and every flag is reported as answered.

- **Test:** `tests/test_engine_binary_flags.py::test_a_binary_that_answers_every_flag_passes`

### Requirement: The flags a user types are exercised, and the families must answer

The probe SHALL execute the standard trio (`--version`, `-h`, `--help`) in addition to the documented
flags, and SHALL require an answer from the help family (`-h` or `--help`) and from the version family
(`--version` or `-V`), so a release that drops a whole family reds while an engine that spells it one
way keeps passing.

WHEN the per-flag verdicts are decided
THEN a missing help-family answer and a missing version-family answer are failures naming the members probed.

#### Scenario: no help spelling answers

Given a binary that answers `--version` and exits 1 for both `-h` and `--help`
When  the verdicts are decided
Then  the failure names the help family and both probed spellings.

- **Test:** `tests/test_engine_binary_flags.py::test_no_help_spelling_reds_the_help_family`

### Requirement: An engine that documents no flags still needs one answer

An engine whose manifest lists no flags SHALL fall back to the standard trio and SHALL fail when none
of them answers — the same guarantee as before, stated explicitly.

WHEN the documented flag list is empty
THEN at least one trio flag must answer, and the failure names the trio when none does.

#### Scenario: an empty manifest still requires an answer

Given an engine whose manifest documents no flags and a binary that exits 1 for every flag
When  the verdicts are decided
Then  the check fails and names the probed trio.

- **Test:** `tests/test_engine_binary_flags.py::test_an_empty_manifest_still_requires_one_answer`

### Requirement: A device-bound CLI is contained, not failed

A variant whose manifest says `probe: device` SHALL pass when the binary file exists and every flag
fails, because its CLI initialises the device at startup and cannot answer on a device-less runner;
its version stays proven by the image's own `detect`.

WHEN a `probe: device` variant answers no flag
THEN the check passes with the containment reason printed.

#### Scenario: a device CLI that cannot answer is contained

Given a manifest with `probe: device` and a binary that exits 1 for every flag
When  the verdicts are decided
Then  the check passes and says the version comes from the image's detect.

- **Test:** `tests/test_engine_binary_flags.py::test_a_device_probe_is_contained_not_failed`

### Requirement: The probe reports per flag instead of short-circuiting

The shipped probe script SHALL execute every requested flag and print one machine-readable verdict per
flag, keeping the exit-code contract (1 = the binary file is missing). The decision SHALL live in the
parsed result, never in the probe's own first success.

WHEN the probe runs against a binary that answers the first flag and fails the second
THEN it prints a verdict line for both flags and exits 0.

#### Scenario: the probe reports both flags instead of stopping at the first

Given a binary that answers `--version` and exits 1 for `--help`
When  the probe runs with both flags
Then  it exits 0 and carries a verdict line for `--version` and for `--help`.

- **Test:** `tests/test_engine_binary_flags.py::test_the_probe_reports_every_flag_instead_of_stopping_at_the_first`

#### Scenario: a missing binary file is still the probe's failure

Given a path that is not an executable file anywhere on PATH
When  the probe runs
Then  it exits 1 and says which binary file it could not find.

- **Test:** `tests/test_engine_binary_flags.py::test_a_missing_binary_file_is_still_the_probe_failure`
