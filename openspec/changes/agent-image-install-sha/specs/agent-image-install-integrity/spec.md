## ADDED Requirements

### Requirement: The fetched Hermes installer is verified against a pinned content hash

The agent image's Hermes install step SHALL download the installer from
`HERMES_INSTALL_URL` to a file and verify its sha256 against
`HERMES_INSTALL_SCRIPT_SHA` (a Dockerfile ARG pin, exported via ENV) BEFORE
executing it. A content mismatch SHALL fail the install step non-zero. The
fetched script SHALL NOT be piped into `bash` unverified.

#### Scenario: drift fails the install

- **WHEN** the install step runs with a pinned sha that does not match the fetched script
- **THEN** it prints a content-drift refusal and exits non-zero without executing the installer

#### Scenario: verified script runs with its pinned args

- **WHEN** verification passes
- **THEN** the installer runs from the temp file with `${HERMES_INSTALL_ARGS:-}` forwarded

### Requirement: The pin and the verify order are locked by tests

A test SHALL assert the Dockerfile carries `ARG HERMES_INSTALL_SCRIPT_SHA`
with a 64-hex default, exports it to the install step via ENV, and that the
install script's statements run in fetch → verify → execute order.

#### Scenario: seam drift reddens the unit battery

- **WHEN** the pin, the ENV wiring, or the verify-before-run order is removed
- **THEN** `tests/test_agent_image_refresh.py` fails
