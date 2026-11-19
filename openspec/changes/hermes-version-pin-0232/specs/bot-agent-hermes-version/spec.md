# bot-agent-hermes-version

## ADDED Requirements

### Requirement: The agent image pins the Hermes install to v0.23.2

The agent image SHALL install the Hermes CLI from exactly the v0.23.2 release: the Dockerfile's
`HERMES_INSTALL_ARGS` SHALL forward install.sh's `--commit <peeled-v0.23.2-commit>` flag (so the
checkout is the v0.23.2 tag commit, not whatever `stable` resolves to at build time), and the
install script SHALL read the installed CLI back and fail the build unless the first version token
equals the pinned version.

WHEN the agent image is built
THEN install.sh checks out `ae2a81ccc00e9b7c06301523e5bb09608397149c` (v0.23.2), and
      `install_hermes_ci.sh` fails the build unless `hermes --version`'s first token is `0.23.2`.

#### Scenario: the committed pin carries the version and the peeled commit everywhere

Given the repository as committed
When  `make check-agent-model` runs and the test suite selects `-k version`
Then  the referee reports the Dockerfile's `ARG HERMES_VERSION` and `ARG HERMES_INSTALL_COMMIT`
      and the install script's `VERSION` default all matching `0.23.2` / the peeled v0.23.2 commit,
      and exits zero.

- **Test:** `tests/test_agent_model_pin.py::test_the_committed_hermes_version_pin_matches_the_one_declared_value`,
  `tests/test_agent_model_pin.py::test_the_dockerfile_forwards_the_pinned_commit_to_install_sh`

#### Scenario: a drifted version in the Dockerfile is reported, not ignored

Given a Dockerfile whose `ARG HERMES_VERSION` default names a different release
When  the referee runs against that tree
Then  it exits non-zero naming the Dockerfile's version ARG and the value it read.

- **Test:** `tests/test_agent_model_pin.py::test_a_drifted_version_in_the_dockerfile_is_a_finding`

#### Scenario: a drifted version in the install script is reported too

Given an install script whose `VERSION` default names a different release
When  the referee runs against that tree
Then  it exits non-zero naming the install script's version default.

- **Test:** `tests/test_agent_model_pin.py::test_a_drifted_version_in_the_install_script_is_a_finding`

#### Scenario: a drifted commit in the Dockerfile is reported too

Given a Dockerfile whose `ARG HERMES_INSTALL_COMMIT` default names a different commit
When  the referee runs against that tree
Then  it exits non-zero naming the drifted commit ARG (which docker would resolve into the args).

- **Test:** `tests/test_agent_model_pin.py::test_a_drifted_commit_in_the_dockerfile_is_a_finding`

#### Scenario: a dropped --commit flag is reported too

Given a Dockerfile whose `HERMES_INSTALL_ARGS` no longer forwards the `--commit` flag
When  the referee runs against that tree
Then  it exits non-zero naming the missing `--commit` forward (the install would float).

- **Test:** `tests/test_agent_model_pin.py::test_a_dropped_commit_flag_in_the_dockerfile_is_a_finding`

### Requirement: The install script reads the installed version back and fails loudly on a mismatch

The install script SHALL run `hermes --version` after install and fail the build unless the first
token of the installed version equals the pinned `VERSION` default (`0.23.2`), so a build that
installed any other Hermes fails at build time instead of serving the bots a surprise.

WHEN `install_hermes_ci.sh` finishes installing
THEN it reads the installed CLI version and fails unless the first token equals the pinned version.

#### Scenario: the install script asserts the installed version

Given the install script's post-install block
When  it is read
Then  it compares the first token of `hermes --version` against the pinned `VERSION` default and
      exits non-zero on a mismatch.

- **Test:** `tests/test_agent_model_pin.py::test_the_committed_hermes_version_pin_matches_the_one_declared_value`
  (asserts the script carries the `VERSION="${HERMES_VERSION:-…}"` default and the `--version`
   read-back in `tests/test_agent_image_refresh.py` still passes).
