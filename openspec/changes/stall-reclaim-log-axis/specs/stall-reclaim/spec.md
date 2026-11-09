# stall-reclaim

## MODIFIED Requirements

### Requirement: the stall detector classifies on the lane session log and API counter, never the per-run kanban log

A task's log axis reads `$HOME/.hermes/profiles/<lane>/logs/agent.log` (where `<lane>`
is `task_runs.profile`) and the last `API call #<N>` counter in that file — never
`$KANBAN_HOME/kanban/logs/<task>.log` and never `last_heartbeat_at`,
`max_runtime_seconds` or bare task status. Each verdict is taken from **two samples
≥ 60 s apart**. A task is `ACTIVE` when EITHER the `agent.log` mtime advanced across
the samples OR the `API call #N` counter rose between them.

WHEN a candidate task is sampled twice ≥ 60 s apart and its lane `agent.log` mtime
advanced between the samples, or its last `API call #N` rose
THEN its log axis is fresh and the task reads `ACTIVE` (never STALLED purely on an old
kanban log or a ~0 CPU delta).

WHEN a candidate task is sampled twice and neither the `agent.log` mtime nor the
`API call #N` counter advanced, and its CPU delta is ~0
THEN it reads `STALLED`.

#### Scenario: an advancing agent.log makes a worker ACTIVE despite an old kanban log

- **Given** a worker whose process age and CPU delta are old/idle (~0 ticks) but whose lane `agent.log` mtime advanced between two samples ≥ 60 s apart
- **When** the sweep classifies it
- **Then** it reads `ACTIVE` — the per-run `<kanban>/logs/<task>.log` age never makes it STALLED
- **Test:** `tests/test_stall_reclaim.py::test_advancing_agent_log_is_active_with_old_kanban_log_and_0_cpu`

#### Scenario: a no-log-write, no-API, ~0-CPU worker reads STALLED

- **Given** a worker with no `agent.log` write, no `API call #N` advance, and ~0 CPU over two samples ≥ 60 s apart
- **When** the sweep classifies it
- **Then** it reads `STALLED`
- **Test:** `tests/test_stall_reclaim.py::test_no_log_and_no_api_and_idle_is_stalled`

#### Scenario: `last_heartbeat_at`, `max_runtime_seconds` and bare task status are never operands

- **Given** a task classified by the sweep
- **When** its operands are gathered
- **Then** none of `last_heartbeat_at`, `max_runtime_seconds`, or the bare `running` status are read as a work signal
- **Test:** `tests/test_stall_reclaim.py::test_unused_database_fields_are_not_operands`

### Requirement: two consecutive STALLED verdicts are required before any reclaim

A single STALLED reading is never acted on. A task must read STALLED on two consecutive
verdicts (each verdict itself built from two samples ≥ 60 s apart) before any
`kanban reclaim` / `kanban block` is attempted.

WHEN a task reads STALLED once but the second consecutive verdict is ACTIVE or YOUNG
THEN no action is taken for it.

WHEN a task reads STALLED on two consecutive verdicts
THEN it becomes a reclaim candidate.

#### Scenario: one STALLED verdict never acts

- **Given** a task whose first verdict is STALLED and whose second consecutive verdict is ACTIVE
- **When** the sweep decides whether to act
- **Then** no reclaim is attempted and it is not counted as a reclaimed task
- **Test:** `tests/test_stall_reclaim.py::test_two_consecutive_stalled_verdicts_required`

### Requirement: every verdict line prints both samples' operands

Each task's verdict line prints both samples of every operand, e.g.
`STALLED t_x pid=N age=34m log=34m api=#41->#41 cpu=1t/1t samples=2` and
`ACTIVE  t_y pid=N age=21m log=0.4m api=#12->#15 cpu=3t/2t samples=2`.

WHEN a task's verdict is emitted
THEN the line shows the before->after value of `api` and `cpu` (and one scalar for
`age` / `log`) plus `samples=2`.

#### Scenario: operands are printed per sample

- **Given** a verdict line produced by the sweep
- **Then** it contains both samples' `api=#A->#B`, `cpu=X/Y`, and `samples=2`
- **Test:** `tests/test_stall_reclaim.py::test_verdict_line_prints_both_samples_operands`

### Requirement: the kanban path never signals a worker pid

The kanban path acts only through `kanban reclaim`, and `kanban block` when the churn
cap trips. No `kill`, `os.kill` or `SIGTERM`/`SIGKILL` is reachable from the kanban
classification/action path. The separate DM-waiter reaper
(`pgrep -f bot_mode_dm.py`) may keep SIGTERM/SIGKILL but is its own function whose
pid source is its own pgrep enumeration — a pid sourced from `task_runs` can never
reach it.

WHEN the source of a stalled kanban worker's pid is a `task_runs.worker_pid`
THEN the only action available is `kanban reclaim` / `kanban block` — the code path
contains no signal primitive.

WHEN the DM-waiter reaper runs
THEN it enumerates its own pids via `pgrep -f bot_mode_dm.py` and only ever signals a
pid it found there, never one supplied from `task_runs`.

#### Scenario: no kill is reachable from the kanban action path

- **Given** the sweep module source
- **When** the kanban classification/action section is inspected
- **Then** it contains no `kill`, `os.kill`, `SIGTERM` or `SIGKILL` reachable from it
- **Test:** `tests/test_stall_reclaim.py::test_kanban_path_has_no_signal_primitive`

#### Scenario: a task_runs pid can never reach the DM reaper

- **Given** the DM-waiter reaper function
- **When** its pid source is inspected
- **Then** it enumerates only `pgrep -f bot_mode_dm.py` and never consumes a `task_runs` `worker_pid`
- **Test:** `tests/test_stall_reclaim.py::test_task_runs_pid_never_reaches_dm_reaper`

### Requirement: allowlist and churn cap are preserved

Only a pid whose cmdline is a kanban worker AND whose task the DB records `running` is
a candidate. Reclaims are capped at `MAX_RECLAIMS` (3) inside `STATE_WINDOW_H` (6 h);
state lives in `$HOME/.hermes/kanban/.stall_reclaims.json`, is written only on a real
reclaim (a DRY run leaves no file), and stale entries are pruned.

WHEN a pid is not a kanban worker, or its task is not recorded `running`
THEN it is never a candidate.

WHEN a task has been reclaimed `MAX_RECLAIMS` times inside the window
THEN the sweep `kanban block`s it instead of recycling it.

WHEN the sweep runs in DRY mode
THEN no state file is created or modified.

#### Scenario: non-worker and unknown-task pids are never candidates

- **Given** a pid whose cmdline is not a kanban worker, and a task not recorded `running`
- **When** the sweep enumerates candidates
- **Then** neither becomes a candidate
- **Test:** `tests/test_stall_reclaim.py::test_allowlist_rejects_non_worker_and_unknown`

#### Scenario: the churn cap blocks after the third reclaim

- **Given** a task with 3 reclaims recorded inside the window
- **When** it is a STALLED candidate
- **Then** it is `kanban block`ed, not recycled
- **Test:** `tests/test_stall_reclaim.py::test_churn_cap_blocks_after_max_reclaims`

#### Scenario: a DRY run leaves no state file

- **Given** a DRY sweep with a task that would be reclaimed
- **When** it completes
- **Then** no `.stall_reclaims.json` file exists
- **Test:** `tests/test_stall_reclaim.py::test_dry_run_creates_no_state_file`

### Requirement: negative control — nothing stale changes nothing

When no candidate reads STALLED, the sweep prints `tasks: stalled=0`, touches no task,
and creates no state file.

WHEN every running task reads ACTIVE or YOUNG
THEN the sweep prints `tasks: stalled=0`, changes nothing, and creates no state file.

#### Scenario: a healthy board is untouched

- **Given** only healthy (advancing-log or busy-CPU) workers
- **When** the sweep runs in APPLY mode
- **Then** it prints `tasks: stalled=0` and performs no reclaim and writes no state file
- **Test:** `tests/test_stall_reclaim.py::test_negative_control_stalled_zero_changes_nothing`

### Requirement: the threshold matrix is preserved

- fresh process -> YOUNG
- old process + fresh log -> YOUNG
- old + stale log + busy CPU -> ACTIVE
- old + stale + idle -> STALLED

WHEN a worker's process age is below `STALL_MIN`
THEN it reads YOUNG and is never a candidate.

WHEN a worker's process is old but none of its log/CPU signals advanced during the
window and its `agent.log` is itself fresh (age below `STALL_MIN`)
THEN it reads YOUNG.

WHEN a worker's process and log are old, its log axis did not advance, and its CPU
delta exceeds `MAX_CPU_TICKS`
THEN it reads ACTIVE.

WHEN a worker's process and log are old, its log axis did not advance, and its CPU
delta is within `MAX_CPU_TICKS`
THEN it reads STALLED.

#### Scenario: the threshold matrix verdicts

- **Given** workers exercising each cell of the matrix
- **When** they are classified
- **Then** fresh-process is YOUNG, old+fresh-log is YOUNG, old+stale+busy is ACTIVE, and old+stale+idle is STALLED
- **Test:** `tests/test_stall_reclaim.py::test_threshold_matrix`
