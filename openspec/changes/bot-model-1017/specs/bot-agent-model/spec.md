# bot-agent-model

## ADDED Requirements

### Requirement: One pinned snapshot, enforced

Every place that pins the model the bots call SHALL name the same provider-prefixed snapshot id
(`deepseek/deepseek-v4.1-flash-1017`), and a deterministic gate SHALL fail — naming the file and the
value it read — when the agent image's Dockerfile, the image's install script, or the model id they
declare disagree, or name a different DeepSeek V4.1 Flash snapshot.

WHEN the model pin is read from the Dockerfile and from the install script
THEN both SHALL equal the single value `scripts/agent_model_pin.py` declares, and the gate SHALL exit
non-zero otherwise.

#### Scenario: the committed pin is the current snapshot everywhere

Given the repository as committed
When  `make check-agent-model` runs
Then  it reports the Dockerfile and the install script both carrying
      `deepseek/deepseek-v4.1-flash-1017` and exits zero.

- **Test:** `tests/test_agent_model_pin.py::test_the_committed_pin_matches_the_one_declared_value`

#### Scenario: an older snapshot in the Dockerfile is reported, not ignored

Given a Dockerfile whose `ARG HERMES_MODEL_ID` default is the unpinned `deepseek/deepseek-v4.1-flash`
When  the checker runs against that tree
Then  it exits non-zero naming the Dockerfile and the value it read, and names no other file as
      the culprit.

- **Test:** `tests/test_agent_model_pin.py::test_a_stale_default_in_the_dockerfile_is_a_finding`

#### Scenario: a newer snapshot in the install script is reported too

Given an install script whose `MODEL_ID` default is `deepseek/deepseek-v4.1-flash-1102`
When  the checker runs against that tree
Then  it exits non-zero naming the install script — a substring assert would have called this green,
      which is how the drift shipped.

- **Test:** `tests/test_agent_model_pin.py::test_a_different_snapshot_in_the_install_script_is_a_finding`

#### Scenario: the gate is reached by the pipeline that builds the image

Given the Makefile's `ci-unit` recipe and the wiring graph
When  `ci-unit`'s command line is read
Then  it runs `make check-agent-model`, and both new targets are declared `.PHONY`.

- **Test:** `tests/test_agent_model_pin.py::test_ci_unit_runs_the_check_and_the_targets_are_phony`

### Requirement: The alias carries the model's real budget

The install script SHALL write `max_tokens` and `context_window` on the model alias, using the values
the catalogue publishes for `deepseek/deepseek-v4.1-flash-1017` (`context_length: 1048576`), and the
image build SHALL assert all three keys (`model`, `max_tokens`, `context_window`) landed — so an alias
that Hermes would budget from a default fails the build instead of a 120-minute bot run.

WHEN the agent image is built
THEN the build fails unless the alias's model id, `max_tokens` and `context_window` are the pinned
values.

#### Scenario: the build asserts the whole alias, not just its name

Given the agent Dockerfile's verification step
When  its assertions are read
Then  it checks `model.aliases.<alias>.model`, `.max_tokens` and `.context_window` against the build
      args, and the install script writes all three.

- **Test:** `tests/test_agent_model_pin.py::test_the_image_writes_and_asserts_the_alias_budget`

#### Scenario: the context window matches what the model publishes

Given the pinned snapshot's published `context_length`
When  the values in `scripts/agent_model_pin.py` are compared with it
Then  `CONTEXT_WINDOW` equals `1048576` and `MAX_TOKENS` is a positive budget below it.

- **Test:** `tests/test_agent_model_pin.py::test_the_context_window_matches_the_published_length`
