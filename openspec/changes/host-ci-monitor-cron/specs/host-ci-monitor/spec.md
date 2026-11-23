# host-ci-monitor — specs

## ADDED Requirements

### Requirement: `make ci-monitor` prints a deterministic gh-backed incident snapshot

`scripts/ci_monitor.py`, run through the `ci-monitor` Makefile target against `$(GH_REPO)`, MUST print
the incident snapshot of the repo using read-only `gh` reads only: completed `main`-branch runs whose
conclusion is `failure`, `cancelled`, or `timed_out`; open non-draft PRs whose check buckets contain a
`fail`; open PRs whose `mergeStateStatus` is `DIRTY` or `BEHIND`; and open PRs whose `reviewDecision`
is `CHANGES_REQUESTED`. Snapshot lines MUST be `MAIN-RED run=<id> workflow=<name> conclusion=<c>`,
`PR-CHECKS pr=<n> head=<sha9> failed=<k>`, `PR-MERGE pr=<n> head=<sha9> merge=<state>`, and
`PR-REVIEW pr=<n> head=<sha9> decision=CHANGES_REQUESTED` respectively, sorted lexicographically, and
MUST NOT contain timestamps or other values that change while the incident set is unchanged. A board
with no incident MUST print exactly `MONITOR-OK`; a failed `gh` fetch MUST print the stable line
`MONITOR-ERROR gh-fetch-failed` with the detail on stderr. The monitor MUST NOT start, rerun, cancel,
or dispatch any pipeline (read-only). A completed red `main` run counts as an incident only while its
`updatedAt` is within the age window (`MAX_AGE_HOURS`, default 72, via the `ci-monitor` target), so
batched cancels and old failures age out instead of keeping the board permanently red; payloads without
`updatedAt` are never age-filtered.

#### Scenario: a red main run is a MAIN-RED line

- **Given** a recorded main-run payload where one completed run has conclusion `failure`
- **When** the snapshot is built
- **Then** the output contains `MAIN-RED run=<that run id> workflow=<name> conclusion=failure`
- **And** green/skipped/in-flight runs produce no lines
- **Test:** `tests/test_ci_monitor.py::test_main_red_line`

#### Scenario: red runs older than the age window are not incidents

- **Given** recorded red main runs stamped 7 days old, 1 hour old, and unstamped, with a fixed `now`
- **When** the snapshot is built with `max_age_hours=72`
- **Then** only the 1-hour-old and the unstamped runs produce `MAIN-RED` lines
- **Test:** `tests/test_ci_monitor.py::test_old_red_runs_age_out_of_the_window`

#### Scenario: failing PR checks and DIRTY/BEHIND merge states are lines

- **Given** recorded open-PR payloads: one PR with two `fail` check buckets, one PR with
  `mergeStateStatus` `DIRTY`, one PR with `BEHIND`, one with `CHANGES_REQUESTED` review, one fully
  green `CLEAN` PR, and one draft PR with failing checks
- **When** the snapshot is built
- **Then** `PR-CHECKS pr=<n> head=<sha9> failed=2`, `PR-MERGE ... merge=DIRTY`, `PR-MERGE ... merge=BEHIND`
  and `PR-REVIEW ... decision=CHANGES_REQUESTED` lines appear, the green PR and the draft PR produce no lines
- **Test:** `tests/test_ci_monitor.py::test_pr_incident_lines`

#### Scenario: a clean board is exactly MONITOR-OK and the snapshot is byte-stable

- **Given** a recorded payload with no incident
- **When** the snapshot is built twice from the same payload
- **Then** both outputs are exactly `MONITOR-OK` and byte-identical
- **Test:** `tests/test_ci_monitor.py::test_clean_board_and_stability`

#### Scenario: a failed gh fetch is a stable MONITOR-ERROR line

- **Given** an injected fetch seam that raises
- **When** the snapshot is built
- **Then** stdout is exactly `MONITOR-ERROR gh-fetch-failed` and the exception detail goes to stderr
- **Test:** `tests/test_ci_monitor.py::test_fetch_failure_line`

### Requirement: the snapshot reads gh only through an injectable fetch seam

`scripts/ci_monitor.py` MUST assemble the snapshot from a `fetch` object injectable in place of the
default `gh`-calling implementation (which goes through the `scripts/proc.py` policy seam), so the
unit battery exercises every snapshot shape against recorded payloads without network, and MUST keep
`make check-wiring` green (script wired to the `ci-monitor` target, module tested).

#### Scenario: tests replace the fetch seam wholesale

- **Given** `tests/test_ci_monitor.py`
- **When** the snapshot is built with a fake fetch returning recorded payloads
- **Then** no `gh` subprocess is spawned during the test
- **Test:** `tests/test_ci_monitor.py` (all cases use the injected seam)

### Requirement: exactly one sanctioned host cron job is the CI monitor

The Hermes gateway on this host MUST carry exactly one active cron job — `llgenie-ci-monitor` on
profile `llgenie-ci-pipelines-maintainer` — created with `--monitor-script
~/.hermes/scripts/llgenie_ci_monitor.py` (a wrapper whose stdout is `make ci-monitor`'s stdout, and
whose output is stable while the incident set is unchanged), `--workdir` at the repo root so the
repo's `AGENTS.md` is injected as the cron agent's project context, and `--deliver local`. Every other
profile cron store MUST stay empty or paused. An unchanged monitor snapshot suppresses the agent run
entirely; a changed snapshot dispatches exactly one agent run (no fan-out, no kanban worker).

#### Scenario: the monitor job exists once and is monitor-gated

- **Given** the host after this change lands
- **When** `hermes -p llgenie-ci-pipelines-maintainer cron list` and `hermes cron list` (default) are run
- **Then** exactly one `[active]` job named `llgenie-ci-monitor` exists on the maintainer profile,
  its monitor script is the wrapper over `make ci-monitor`, and every other store is empty/paused
- **Test:** recorded proof in the issue/PR body from `hermes -p llgenie-ci-pipelines-maintainer cron list`

### Requirement: the cron agent triages incidents and keeps the board moving, single-lane

The monitor job's prompt MUST instruct the cron agent to act on the snapshot diff per `AGENTS.md`:
read the failed run logs (`gh run view --log-failed`) and PR checks, find the root cause, file or link
a six-section issue for the defect, fix on a dedicated worktree behind an OpenSpec change, verify with
the Makefile gates locally, push the branch and open the PR, arm it green+`CLEAN` — and NEVER merge by
hand, never queue-pump (no `gh run rerun`, no dispatch of its own accord), never touch draft PRs. When
the snapshot is clean and no lane PR is open, the job MUST instead take the next open board issue and
drive it end-to-end (issue → OpenSpec change → worktree branch → gates → PR), holding exactly one lane
at a time.

#### Scenario: AGENTS.md carries the ban-plus-exception rule

- **Given** `AGENTS.md` after this change
- **When** the "Hermes cron jobs never run on the host" section is read
- **Then** it bans all host cron dispatch except the named `llgenie-ci-monitor` job, records its
  one-lane / no-queue-pump / no-hand-merge / no-draft-PR contract and the clean-board continuation,
  and `make check-docs` passes
- **Test:** `make check-docs` + the section diff in the PR
