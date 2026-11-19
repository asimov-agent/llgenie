## ADDED Requirements

### Requirement: The Hermes CLI version the agent image installs is pinned through install.sh

The agent image SHALL install the Hermes CLI through the official install.sh at an exact commit:
`containers/agent/Dockerfile` SHALL declare `ARG HERMES_VERSION="0.23.2"` and
`ARG HERMES_INSTALL_COMMIT="ae2a81ccc00e9b7c06301523e5bb09608397149c"` (the peeled commit of the
upstream annotated tag v0.23.2), and `HERMES_INSTALL_ARGS` SHALL carry
`--commit ${HERMES_INSTALL_COMMIT}` alongside the skip flags. A floating `stable`-channel
checkout is not acceptable: the installed release must be named by the tree that builds it.

#### Scenario: The pin names the release in one place each

- **WHEN** the Dockerfile is read
- **THEN** it carries `ARG HERMES_VERSION` with the declared version, `ARG HERMES_INSTALL_COMMIT`
  with the peeled v0.23.2 commit, and its `HERMES_INSTALL_ARGS` default passes that ARG to
  install.sh via `--commit ${HERMES_INSTALL_COMMIT}`

#### Scenario: The version reaches the install step

- **WHEN** the Dockerfile's ENV block is read
- **THEN** `HERMES_VERSION` is forwarded, so `scripts/install_hermes_ci.sh` can check the CLI it
  just installed against it

### Requirement: The installed CLI version is read back at build time

`scripts/install_hermes_ci.sh` SHALL run `hermes --version` after the install step (any install
path) and SHALL exit non-zero unless the first version token equals the pinned
`HERMES_VERSION` default it declares. A drifted or suffixed version (e.g. `0.23.1+6066`) is a
build failure, not a warning.

#### Scenario: A wrong installed version fails the build

- **WHEN** the installed `hermes --version` reports a version other than the declared pin
- **THEN** the script exits non-zero naming both versions

### Requirement: The version pin has one referee and drift reddens the existing gate

`scripts/agent_model_pin.py` SHALL declare the Hermes version and install commit as constants and
compare them against the Dockerfile ARGs and the install script's `HERMES_VERSION` default, in
the same `check` that `make check-agent-model` already runs. A different version in any home is
drift, never "close enough".

#### Scenario: The committed tree passes the referee

- **WHEN** `make check-agent-model` runs against the tree as committed
- **THEN** it exits 0 and the report names version 0.23.2 with the peeled commit

#### Scenario: Drift in either home is caught

- **WHEN** a test rewrites the Dockerfile's `ARG HERMES_VERSION` or the install script's
  `HERMES_VERSION` default to another value
- **THEN** the referee names the file and the offending value and exits non-zero
