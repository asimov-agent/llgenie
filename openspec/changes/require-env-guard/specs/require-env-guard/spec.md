# require-env-guard — spec delta

Capability: `require-env-guard`
Issue: [#363](https://github.com/asimov-agent/llgenie/issues/363)

## ADDED Requirements

### Requirement: a missing or empty credential is a loud failure

`scripts/require_env.py` SHALL exit 2 on the first missing or empty variable, SHALL name that variable,
SHALL print no value (not a prefix, not a length), and SHALL refuse an argument that is not a variable
name.

WHEN a leg's key is missing or empty,
THEN the guard SHALL fail before any work is done.

#### Scenario: a missing key exits 2 and names the variable
Given no `NOUS_API_KEY` in the environment,
When   the guard runs with that name,
Then   it exits 2, its message names `NOUS_API_KEY`, and no value appears.
- **Test:** `tests/test_require_env.py::test_a_missing_key_exits_2_and_names_the_variable`

#### Scenario: an empty key is treated as missing
Given `NOUS_API_KEY` set to an empty string,
When   the guard runs,
Then   it exits 2 exactly as for an unset key.
- **Test:** `tests/test_require_env.py::test_an_empty_key_is_treated_as_missing`

#### Scenario: a present key passes without being printed
Given `NOUS_API_KEY` set to a sentinel,
When   the guard runs,
Then   it exits 0, names the variable, and the sentinel appears in no output.
- **Test:** `tests/test_require_env.py::test_a_present_key_passes_and_is_never_printed`

#### Scenario: a name that is not a variable is refused
Given the argument `not-a-name`,
When   the guard runs,
Then   it exits 2 and says the argument is not a variable name.
- **Test:** `tests/test_require_env.py::test_a_name_that_is_not_a_variable_is_refused`

### Requirement: every agent leg guards before it pulls the image

Every make target that starts the agent image SHALL run the guard as its first recipe line, ahead of
`scripts/ci_images.py ensure agent`, with the keys that leg forwards. The roster SHALL be derived from
the Makefile by the suite, never maintained by hand.

WHEN a leg starts,
THEN the guard SHALL have passed before the image is ensured.

#### Scenario: the roster is derived and every leg is covered
Given every target whose body names `$(AGENT_IMAGE)`,
When   the suite inspects the Makefile,
Then   each runs `python3 scripts/require_env.py`, and the guard precedes the image ensure.
- **Test:** `tests/test_require_env.py::test_every_agent_leg_guards_before_it_pulls_the_image`

### Requirement: the guard is one code path

The ad-hoc bash guard previously carried by `hermes-smoke` SHALL be replaced by the script, in both the
public and the internal recipe, so no second guard can drift from it.

WHEN the Makefile is read,
THEN it contains no `test -n "$$NOUS_API_KEY"` and at least one guard per agent leg.

#### Scenario: the old bash guard is gone
Given the Makefile,
When   the suite searches for the ad-hoc bash test that `hermes-smoke` used to carry,
Then   it finds none, and the guard count is at least the number of agent legs.
- **Test:** `tests/test_require_env.py::test_the_guard_is_one_code_path`
