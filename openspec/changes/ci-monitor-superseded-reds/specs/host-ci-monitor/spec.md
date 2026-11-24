# Spec Delta: ci-monitor-superseded-reds

## ADDED Requirements

### Requirement: a main red is judged by its workflow's newest completed run on main

The monitor SHALL treat a `main` workflow as incident-red only when the **newest completed run of
that workflow on `main`** concluded `failure`, `cancelled` or `timed_out`. A completed red main run
that a newer completed main run of the same workflow superseded (that newer run concluded anything
else) SHALL NOT be an incident: it SHALL NOT appear as a `MAIN-RED` line and SHALL NOT be routed by
`make ci-monitor-triage`. A newer run that is still in flight (not completed) SHALL NOT supersede an
older red, because the workflow's current outcome is not yet known. Supersession is decided inside
the monitor, so the snapshot and the triage keep one incident definition and can never disagree.

#### Scenario: a red that a newer green main run superseded is not an incident

- **Given** a recorded main-run payload where workflow `ci-verdict.yml` ran red at `run=1` and a
  newer completed `ci-verdict.yml` run on `main` concluded `success` at `run=2`
- **When** `classify_main_runs` runs over the payload
- **Then** the incident list contains no `run=1` and the superseded list contains `run=1` with
  `superseded_by=run=2`, and `snapshot_lines` prints no `MAIN-RED` line for it
- **Test:** `tests/test_ci_monitor.py` (recorded payload, rc=0)

#### Scenario: a workflow whose newest completed main run is still red stays an incident

- **Given** a recorded payload where a workflow ran red at `run=1` and again red at the newer
  `run=2`
- **When** `classify_main_runs` runs over the payload
- **Then** `run=2` is an incident printed as `MAIN-RED` and `run=1` is superseded by it
- **Test:** `tests/test_ci_monitor.py` (recorded payload, rc=0)

#### Scenario: a newer run still in flight does not supersede

- **Given** a recorded payload where a workflow ran red at `run=1` and a newer
  `status=in_progress` run exists at `run=2`
- **When** `classify_main_runs` runs over the payload
- **Then** `run=1` remains the newest completed run and stays a `MAIN-RED` incident
- **Test:** `tests/test_ci_monitor.py` (recorded payload, rc=0)

### Requirement: superseded main reds are visible on request and never filed

The snapshot SHALL default to incidents only, so the cron hash-gate is fed current state. With
`--include-superseded` (`make ci-monitor INCLUDE_SUPERSEDED=1`) the snapshot SHALL additionally
print `MAIN-SUPERSEDED run=<id> workflow=<name> conclusion=<c> superseded_by=<id>` lines, sorted with
the rest, and `make ci-monitor-triage` SHALL NOT route any run named only by such a line.

#### Scenario: the knob shows history without filing it

- **Given** a recorded payload with a superseded main red
- **When** `ci_monitor.main(["--triage", "--dry", "--include-superseded", "--fetch", <seam>])` runs
- **Then** the snapshot prints the `MAIN-SUPERSEDED` line, and no `TRIAGE-MAIN` verdict names that
  run id
- **Test:** `tests/test_ci_monitor.py` (recorded seams, rc=0)

## MODIFIED Requirements

### Requirement: `make ci-monitor-triage` routes every snapshot incident to the run-failure reactor in file-only mode

`make ci-monitor-triage` (`scripts/ci_monitor.py --triage`) MUST print the same byte-stable incident
snapshot as `make ci-monitor`, then route each incident: for every `MAIN-RED` line, the named run id;
for every `PR-CHECKS` line, the completed runs with a failure conclusion on that PR's head sha,
resolved through the injectable fetch seam (`gh run list -c <full-sha>`). Only incidents are routed:
a superseded main run (issue #3048) is never routed, even when `--include-superseded` prints it. Each
resolved failed run is handed to `scripts/run_failure_reactor.py` in `--file-only` mode, and each
routing prints one verdict line (`TRIAGE-MAIN run=<id> …` / `TRIAGE-PR pr=<n> run=<id> …`).
`MONITOR-OK` and `MONITOR-ERROR` route nothing. The triage run MUST NOT dispatch any workflow and MUST
NOT rerun any pipeline; with `DRY=1` it prints the routing plan and files nothing.

#### Scenario: recorded payloads drive a full triage with zero writes

- **Given** recorded main-run, PR, check and per-head run-list payloads
- **When** `ci_monitor.main(["--triage", "--fetch", <seam>, "--dry"])` runs
- **Then** the snapshot lines print unchanged, every MAIN-RED and PR-CHECKS incident names its
  resolved failed run ids in verdict lines, each is routed with `file_only=True`, and no dispatch or
  file call is made
- **Test:** `tests/test_ci_monitor.py` (recorded seams, rc=0)

#### Scenario: a superseded main red is routed by nothing

- **Given** recorded payloads in which a main workflow's red run was superseded by a newer completed
  green run of the same workflow
- **When** `ci_monitor.main(["--triage", "--dry", "--fetch", <seam>])` runs
- **Then** no `MAIN-RED` line and no `TRIAGE-MAIN` verdict names that run id
- **Test:** `tests/test_ci_monitor.py` (recorded seams, rc=0)
