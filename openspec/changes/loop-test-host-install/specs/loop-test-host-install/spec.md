# loop-test-host-install

## ADDED Requirements

### Requirement: the loop's `test` stage asserts the install on the host, not in a container

`make test` MUST NOT name `tests/test_install.py` in its containerized command. On Linux that command
is `$(TEST_RUN)` = `docker run … -e HOME=/root`, and the install tests resolve their artifacts from
`HOME` (`tests/conftest.py`: `BIN = HOME / "bin"`, `MODELS_ROOT = HOME / "models"`). Inside a `--rm`
container `/root/bin/llgenie` cannot exist, so under the no-skip policy those assertions can only ever
fail — the stage is red on every Linux host for a reason unrelated to the change being verified.
`make test` MUST therefore reach the install assertions through `$(MAKE) test-install-host`, which
runs them with the host's `$(PY)` against the real `~/bin/llgenie` and `~/models`.

WHEN `make test` runs on a Linux host
THEN the hermetic files run in the container and the install assertions run on the host, and the
stage can be green when a real `make install` is present.

#### Scenario: the containerized command does not name the install tests

- **Given** the `test:` recipe in the `Makefile`
- **When** its lines containing `$(TEST_RUN)` are read
- **Then** none of them names `tests/test_install.py`
- **Test:** `tests/test_loop_test_stage.py::test_test_stage_does_not_run_install_tests_in_the_container`

#### Scenario: the install assertions still run in the stage, on the host

- **Given** the `test:` and `test-install-host:` recipes in the `Makefile`
- **When** they are read
- **Then** `test` calls `$(MAKE) test-install-host`, and `test-install-host` runs `tests/test_install.py`
  with `$(PY)` (never `$(TEST_RUN)`)
- **Test:** `tests/test_loop_test_stage.py::test_test_stage_calls_the_host_install_verification`,
  `tests/test_loop_test_stage.py::test_host_install_target_runs_the_install_tests_with_the_host_python`

### Requirement: the install assertions are not dropped from every gate

Moving them out of the containerized command MUST NOT remove them from every gate. The same
assertions MUST remain reachable through `test-install-host`, and MUST stay named by a target that
runs them, so the artifact checks cannot silently disappear.

#### Scenario: some target still runs the install tests

- **Given** the `Makefile`
- **When** the targets that name `tests/test_install.py` are read
- **Then** at least one of them runs the file
- **Test:** `tests/test_loop_test_stage.py::test_install_assertions_are_still_in_some_gate`
