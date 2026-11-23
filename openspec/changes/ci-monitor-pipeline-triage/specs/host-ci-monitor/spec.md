# Spec delta: host-ci-monitor (issue #3019)

## MODIFIED Requirements

### Requirement: exactly one sanctioned host cron job is the CI monitor

The Hermes gateway on this host MUST carry exactly one active cron job — `llgenie-ci-monitor` on
profile `llgenie-planner` — created with `--monitor-script
~/.hermes/scripts/llgenie_ci_monitor.py` (a wrapper whose stdout is `make ci-monitor`'s stdout, and
whose output is stable while the incident set is unchanged), `--workdir` at the repo root so the
repo's `AGENTS.md` is injected as the cron agent's project context, and `--deliver local`. Every other
profile cron store MUST stay empty or paused (the pre-#3019 `llgenie-ci-pipelines-maintainer` copy is
paused, not duplicated). An unchanged monitor snapshot suppresses the agent run entirely; a changed
snapshot dispatches exactly one agent run (no fan-out, no kanban worker).

#### Scenario: the monitor job exists once, on the planner profile, monitor-gated

- **Given** the host after this change lands
- **When** `hermes -p llgenie-planner cron list` and `hermes -p llgenie-ci-pipelines-maintainer cron list` are run
- **Then** exactly one `[active]` job named `llgenie-ci-monitor` exists on the planner profile, its
  monitor script is the wrapper over `make ci-monitor`, the maintainer-profile copy is paused, and
  every other store is empty/paused
- **Test:** recorded proof in the issue/PR body from `hermes -p llgenie-planner cron list`

### Requirement: the cron agent triages incidents and keeps the board moving, single-lane

The monitor job's prompt MUST instruct the cron agent to act on the snapshot diff per `AGENTS.md`:
run `make ci-monitor-triage` FIRST so scripted routing files the failure issues (deduped, marker
searched) before any manual triage; then read the failed run logs (`gh run view --log-failed`) and PR
checks, find the root cause, file or link a six-section issue for any defect the scripted route did
not already file, fix on a dedicated worktree behind an OpenSpec change, verify with the Makefile
gates locally, push the branch and open the PR, arm it green+`CLEAN` — and NEVER merge by hand,
never queue-pump (no `gh run rerun`, no dispatch of its own accord), never touch draft PRs. A lane
whose own CI pipeline is in flight MUST NOT idle the agent: while that pipeline runs, the agent takes
the next open board issue. A failed pipeline on an open PR the agent owns is fixed ON ITS BRANCH with
pushed commits (never by reruns). When the snapshot is clean and no lane PR is open, the job MUST
instead take the next open board issue and drive it end-to-end (issue → OpenSpec change → worktree
branch → gates → PR), holding exactly one lane at a time.

#### Scenario: AGENTS.md carries the ban-plus-exception rule with the triage-first tick

- **Given** `AGENTS.md` after this change
- **When** the "Hermes cron jobs never run on the host" and monitor-contract sections are read
- **Then** they ban all host cron dispatch except the named `llgenie-ci-monitor` job on the planner
  profile, record the triage-first tick, the no-idle pacing while a lane's CI runs, the
  fix-the-failed-PR-pipeline-on-its-branch rule, the one-lane / no-queue-pump / no-hand-merge /
  no-draft-PR contract and the clean-board continuation, and `make check-docs` passes
- **Test:** `make check-docs` + the section diff in the PR

## ADDED Requirements

### Requirement: `make ci-monitor-triage` routes every snapshot incident to the run-failure reactor in file-only mode

`make ci-monitor-triage` (`scripts/ci_monitor.py --triage`) MUST print the same byte-stable incident
snapshot as `make ci-monitor`, then route each incident: for every `MAIN-RED` line, the named run id;
for every `PR-CHECKS` line, the completed runs with a failure conclusion on that PR's head sha,
resolved through the injectable fetch seam (`gh run list -c <full-sha>`). Each resolved failed run is
handed to `scripts/run_failure_reactor.py` in `--file-only` mode, and each routing prints one verdict
line (`TRIAGE-MAIN run=<id> …` / `TRIAGE-PR pr=<n> run=<id> …`). `MONITOR-OK` and `MONITOR-ERROR`
route nothing. The triage run MUST NOT dispatch any workflow and MUST NOT rerun any pipeline; with
`DRY=1` it prints the routing plan and files nothing.

#### Scenario: recorded payloads drive a full triage with zero writes

- **Given** recorded main-run, PR, check and per-head run-list payloads
- **When** `ci_monitor.main(["--triage", "--fetch", <seam>, "--dry"])` runs
- **Then** the snapshot lines print unchanged, every MAIN-RED and PR-CHECKS incident names its
  resolved failed run ids in verdict lines, each is routed with `file_only=True`, and no dispatch or
  file call is made
- **Test:** `tests/test_ci_monitor.py` (recorded seams, rc=0)
