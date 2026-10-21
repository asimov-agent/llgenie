# unit-gate-hermetic

## ADDED Requirements

### Requirement: The hermetic unit gate carries no live-Hub work

`make test-unit` SHALL NOT run a test that answers live Hub/GitHub links or downloads a model. Those
tests SHALL be de-selected by exact node id in the roster (`tests/fixtures/unit-suite.json`, `deselect`)
— a dated decision with a reason, never a `-k` expression — and SHALL be run by `make test-hub-live`.

WHEN the gate's selection is computed
THEN the three live-Hub node ids SHALL be absent from it, and `make test-hub-live` SHALL run exactly them.

#### Scenario: the live checks are out of the gate

Given the roster's de-selections as `scripts/unit_tests.py` computes them
When  the gate's argv is built
Then  both live-Hub node ids are `--deselect`ed, so no unit run touches the network.

- **Test:** `tests/test_hub_live_target.py::test_the_live_hub_tests_are_out_of_the_hermetic_gate`

#### Scenario: one target owns the live checks

Given the `test-hub-live` recipe
When  its pytest invocation is read
Then  it names exactly the three node ids, with `-p no:cacheprovider` and no `-k`, and it is `.PHONY`.

- **Test:** `tests/test_hub_live_target.py::test_the_hub_live_target_runs_exactly_those_nodes`

#### Scenario: a de-selection cannot go stale

Given every `deselect` entry in the real roster
When  each named test is looked for in its file
Then  it is still defined, and its reason names the target that runs it — a renamed test cannot silently
      keep shrinking the gate.

- **Test:** `tests/test_hub_live_target.py::test_every_deselection_names_a_test_that_really_exists`

#### Scenario: the de-selection is about these three tests

Given `tests/test_trend_pick.py`
When  the three live checks are looked for
Then  both are defined exactly as the roster and the target name them, so a rename moves the decision
      with it.

- **Test:** `tests/test_hub_live_target.py::test_the_network_tests_still_exist_and_are_the_ones_named`
