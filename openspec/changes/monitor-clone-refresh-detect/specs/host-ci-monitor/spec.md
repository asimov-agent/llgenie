# host-ci-monitor — specs

## ADDED Requirements

### Requirement: the monitor wrapper reports a broken clone refresh as its own stable line

The wrapper `scripts/host_ci_monitor_wrapper.py` (the cron job's `--monitor-script`) refreshes its
dedicated clone before running `make -s ci-monitor`. A failed `git clone`, `git fetch`, or
`git merge --ff-only`, and a dirty clone tree, MUST each print the stable line
`MONITOR-ERROR clone-refresh-failed` on stdout (with the failing command's detail on stderr) and MUST
NOT fall through to `make` on the stale tree. The line `MONITOR-ERROR make-ci-monitor-failed` MUST
then appear only when `make` itself failed against a refreshed, clean clone — so "I could not refresh"
is never read as the tick contract's "the target has not landed yet: do nothing". stdout stays
byte-stable per state class (no timestamps).

#### Scenario: a clone whose fetch fails prints the refresh line, not the not-landed line

- **Given** a monitor clone whose `origin` points at an unreachable local path
- **When** the wrapper module's `main()` runs against it
- **Then** stdout is exactly `MONITOR-ERROR clone-refresh-failed`
- **And** `MONITOR-ERROR make-ci-monitor-failed` does not appear
- **Test:** `tests/test_host_ci_monitor_wrapper.py::test_failed_fetch_prints_clone_refresh_failed`

#### Scenario: a dirty clone prints the same refresh line

- **Given** an otherwise-refreshable monitor clone carrying one untracked file
- **When** the wrapper's `main()` runs
- **Then** stdout is exactly `MONITOR-ERROR clone-refresh-failed`
- **Test:** `tests/test_host_ci_monitor_wrapper.py::test_dirty_clone_prints_clone_refresh_failed`

#### Scenario: a clone genuinely predated the target still prints the not-landed line

- **Given** a clean monitor clone whose Makefile has no `ci-monitor` rule and whose refresh succeeds
- **When** the wrapper's `main()` runs
- **Then** stdout is exactly `MONITOR-ERROR make-ci-monitor-failed` (no false refresh alarm)
- **Test:** `tests/test_host_ci_monitor_wrapper.py::test_pre_target_clone_still_prints_make_failed`

### Requirement: the wrapper passes make's stderr through in every outcome

When `make -s ci-monitor` exits non-zero the wrapper already writes its stderr; when make exits 0 the
wrapper MUST also write make's stderr to its own stderr, so `scripts/ci_monitor.py`'s
`MONITOR-ERROR gh-fetch-failed` detail (printed to stderr by spec) reaches the cron's stderr while
stdout remains the byte-stable snapshot.

#### Scenario: a green snapshot with a stderr detail reaches both streams

- **Given** a fake Makefile whose `ci-monitor` rule exits 0 and prints a detail line to stderr
- **When** the wrapper's `main()` runs against it
- **Then** stdout carries the snapshot and stderr carries the detail line
- **Test:** `tests/test_host_ci_monitor_wrapper.py::test_green_make_stderr_is_passed_through`

### Requirement: the wrapper is repo-canonical with an install target

The wrapper MUST live in the repo at `scripts/host_ci_monitor_wrapper.py` and the host copies
(`~/.hermes/scripts/llgenie_ci_monitor.py` and each profile's `scripts/llgenie_ci_monitor.py`) MUST be
installed from it by `make host-ci-monitor-install`, byte-identical. The host copies are mirrors: a fix
lands in the repo copy and is reinstalled, never hand-edited on the host.

#### Scenario: install copies the repo wrapper byte-identical to the host paths

- **Given** the repo tree with the wrapper
- **When** `make host-ci-monitor-install` runs on this host
- **Then** every installed copy hashes identically to `scripts/host_ci_monitor_wrapper.py`
- **Test:** `make host-ci-monitor-install` + `sha256sum` parity recorded in the issue/PR proof
