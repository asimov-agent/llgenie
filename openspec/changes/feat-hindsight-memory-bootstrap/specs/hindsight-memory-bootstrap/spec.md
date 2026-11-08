# Hindsight memory bootstrap

## ADDED Requirements

### Requirement: install provisions the embedded Hindsight daemon, pinned and idempotent

The fleet's memory is one embedded daemon on `127.0.0.1:9177`. `scripts/memory_bootstrap.py
install` provisions it at a pinned version (`uvx hindsight-api@1.2.0 --idle-timeout 0
--port 9177`), detached from the gateway, and is idempotent: a port already served is
reported as "no change" and exits 0. `--dry-run` prints the command and writes nothing.

#### Scenario: install prints the pinned command and writes nothing under --dry-run
- **Test:** `tests/test_memory_bootstrap.py::test_install_dry_run_prints_the_pinned_command_and_writes_nothing`
Given a `HERMES_HOME` with nothing provisioned,
When  `memory_bootstrap.py install --dry-run` runs,
Then  it exits 0, prints `hindsight-api@1.2.0`, `--idle-timeout 0` and `--port 9177`, and
writes no file under the home.

#### Scenario: install is idempotent when the port is already served
- **Test:** `tests/test_memory_bootstrap.py::test_install_is_idempotent_when_the_port_is_already_served`
Given a real listener already bound to the daemon port,
When  `memory_bootstrap.py install --port <port>` runs a second time,
Then  it exits 0 and reports "no change" and never re-provisions.

#### Scenario: a host without uv is a loud precondition failure
- **Test:** `tests/test_memory_bootstrap.py::test_install_without_uvx_is_a_loud_precondition_failure`
Given `uvx` is not on PATH and the daemon port is free,
When  `memory_bootstrap.py install --port <port>` runs,
Then  it exits 2 and names `uvx`/`uv` as the missing prerequisite.

### Requirement: bootstrap writes each profile's Hindsight wiring from one template, idempotently

`memory_bootstrap.py bootstrap` writes each requested (`llgenie-*`) profile's
`hindsight/config.json`, its `HINDSIGHT_LLM_API_KEY` env key and the memory-provider setting
from one template, reusing the plugin's env builder so bootstrap and runtime agree by
construction. A second run reports `0 updated, N unchanged`. Config and env files are written
`0600`. The bootstrap never prints or copies a credential value, and never invents a key a
profile does not carry.

#### Scenario: a second bootstrap reports zero updates
- **Test:** `tests/test_memory_bootstrap.py::test_bootstrap_is_idempotent_and_reuses_the_plugin_builder`
Given profiles whose `.env` carry their keys,
When  `bootstrap --profiles <a> <b> <c>` runs once and then again,
Then  the first run writes `3 updated`, the second reports `0 updated, 3 unchanged`, and
each profile's config and `.env` are mode `0600`.

### Requirement: dry-run prints the plan and writes nothing
`--dry-run` reports what an applying run would change — the config path, the `0600` mode and
the provider delta — and writes no file.

#### Scenario: dry-run prints the plan and writes nothing
- **Test:** `tests/test_memory_bootstrap.py::test_bootstrap_dry_run_writes_nothing_and_prints_the_plan`
Given profiles with unset providers and keys,
When  `bootstrap --dry-run` runs,
Then  it prints the config path, the mode `0600` and the provider delta, and the tree is
byte-identical afterwards.

### Requirement: the bootstrap never emits a credential value
The key travels from the profile's own `.env` into the daemon env by reference through the
plugin's builder; no step echoes it to stdout, stderr or a committed file.

#### Scenario: the sentinel secret appears nowhere in any run's output
- **Test:** `tests/test_memory_bootstrap.py::test_bootstrap_never_emits_the_credential_to_stdout_or_stderr`
Given a profile whose `.env` carries a distinctive sentinel key,
When  `bootstrap` runs (in real and `--dry-run` modes),
Then  the sentinel (and any key-shaped value) appears nowhere in stdout or stderr.

### Requirement: the bootstrap reuses the plugin's env builder
The bootstrap drives the Hindsight plugin's own env builder (`plugins/hindsight/embedded.py`)
rather than re-implementing it, so the bootstrap and the runtime agree by construction. The
verified env carries the documented model/base-url/provider keys.

#### Scenario: the bootstrap env equals the runtime builder's env
- **Test:** `tests/test_memory_bootstrap.py::test_the_bootstrap_env_equals_the_plugin_runtime_builder`
Given a profile bootstrapped with a key,
When  the plugin's `_build_embedded_profile_env` runs on that profile's template config +
key,
Then  the resulting daemon env carries the documented model/base-url/provider keys, matching
the bootstrap's own template by construction.

### Requirement: verify reports per-profile PASS/FAIL and names failing profiles
`memory_bootstrap.py verify` reports each profile PASS/FAIL with the daemon pid + port and
the newest `Connection verified:` line. A profile whose provider is empty or whose env key is
absent FAILS with its name — never a silent skip.

#### Scenario: a profile with an empty provider or missing key FAILS
- **Test:** `tests/test_memory_bootstrap.py::test_verify_fails_a_profile_with_empty_provider_or_missing_key`
Given one wired profile and one with an empty provider and no key,
When  `verify --profiles <good> <bad>` runs,
Then  it exits 1, prints `<good>: PASS` and `<bad>: FAIL`, names `no HINDSIGHT_LLM_API_KEY`
and the empty provider, and the failing profile is named in stderr.

#### Scenario: a PASS report carries the daemon port and newest Connection verified line
- **Test:** `tests/test_memory_bootstrap.py::test_verify_reports_the_daemon_pid_port_and_connection_line`
Given a wired profile and a daemon log with `Connection verified:` lines,
When  `verify` runs,
Then  it exits 0, prints `llgenie-good: PASS`, carries the port, and reports the newest
connection line.

### Requirement: the verification feeds the gate
`memory-check` runs the verify step and propagates its exit code, reds the board on a failed
profile, and is a declared `.PHONY` target. The ride calls #2058's drift check; it does not
redefine it.

#### Scenario: the gate target wires the verify exit code
- **Test:** `tests/test_memory_bootstrap.py::test_make_targets_wire_install_bootstrap_verify_and_memory_check`
Given the Makefile,
When  `memory-check` is read,
Then  it is in `.PHONY` and its recipe runs `memory_bootstrap.py verify`.
