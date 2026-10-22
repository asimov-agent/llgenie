# strata-download-live

## ADDED Requirements

### Requirement: The Strata download checks are out of the hermetic unit gate

`make test-unit` SHALL NOT run `tests/test_strata_download.py`: the file fetches Strata's pinned commit
over git, reads the live Hub at its pinned revisions and pip-installs the engine's requirements, none of
which is hermetic. The file SHALL be recorded in `tests/fixtures/unit-suite.json` `excluded` with a
reason, issue #437, its date and the target that runs it instead, and `make test-strata-live` SHALL run
it in full.

WHEN the gate's hermetic selection is computed
THEN `tests/test_strata_download.py` SHALL be absent from it, and `make test-strata-live` SHALL run the
file.

#### Scenario: the live file is out of the gate

Given the roster's exclusions as `scripts/unit_tests.py` computes them
When  the hermetic selection is built
Then  `tests/test_strata_download.py` is not in it, so no unit run fetches Strata or reads the Hub.

- **Test:** `tests/test_strata_live_target.py::test_the_strata_download_file_is_out_of_the_hermetic_gate`

#### Scenario: one target owns the live file

Given the `test-strata-live` recipe
When  its pytest invocation is read
Then  it names `tests/test_strata_download.py`, carries `-p no:cacheprovider`, uses no `-k` expression,
      and the target is `.PHONY`.

- **Test:** `tests/test_strata_live_target.py::test_the_strata_live_target_runs_the_whole_file`

#### Scenario: the decision names its issue and its runner

Given the roster entry for `tests/test_strata_download.py`
When  its fields are read
Then  it records issue #437, a real reason, and `target` = `test-strata-live`, which `make` declares.

- **Test:** `tests/test_strata_live_target.py::test_the_roster_entry_names_the_issue_and_its_target`

#### Scenario: a rewritten file cannot leave a stale exclusion

Given `tests/test_strata_download.py`
When  its fixtures are read
Then  it still shallow-fetches the pinned Strata source, so the exclusion still describes the file: a
      rewrite that removes the network work must revisit the roster entry rather than silently keep the
      tests out of the gate.

- **Test:** `tests/test_strata_live_target.py::test_the_file_still_carries_the_fetch_the_decision_names`
