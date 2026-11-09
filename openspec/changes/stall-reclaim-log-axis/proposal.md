# stall-reclaim-log-axis — proposal

Issue: [#2155](https://github.com/asimov-agent/llgenie/issues/2155)

## Why

The orchestrator tick's stall detector measures the wrong log. `stall_reclaim.sh`
reads `log_age_m` from `$KANBAN_HOME/kanban/logs/<task>.log`; that file receives
the session header at spawn and **nothing after it**, so its mtime age is not
"time since the worker last worked" — it is, to the minute, **the process age**.
Measured 2026-11-09: on all eight running tasks `kanbanlog == age`, while the lane
`agent.log` on every row was 0.1–1.8 min old with a rising `API call #N` counter.
A DRY run reported `STALLED t_959810c9 age=29m log=29m cpu=1t` — that worker was
LIVE (`agent.log` 0.3 min old, `API call #44`). Two prior false positives are on the
issue (`00:24Z`, `02:27Z`). `--apply` on that verdict reclaims a working lane, and
the `cap=3/6h` then blocks the next genuine reclaim.

The `cpu` axis is equally uninformative: a worker blocked on a model API response
accrues ~1 tick per sample window, so `cpu <= MAX_CPU_TICKS (5)` holds for every
healthy worker.

## What Changes

The detector's log axis moves to the lane session log and the API-call counter:

- **`agents/llgenie-planner/scripts/stall_reclaim.py`** — a Python port of the
  sweep (pytest-matrixable, per the issue's own implementation-table name). The
  per-run `<kanban>/logs/<task>.log` is **never** a work signal. For each candidate
  task the lane is taken from `task_runs.profile`, and the signals are
  `$HOME/.hermes/profiles/<lane>/logs/agent.log`'s mtime and the last
  `API call #<N>` in that file (`grep -o 'API call #[0-9]*' | tail -1`).
  Each verdict is taken from **two samples ≥ 60 s apart**; a task is `ACTIVE` when
  EITHER the `agent.log` mtime advanced across the samples OR the API-call counter
  rose. **Two consecutive STALLED verdicts** are required before any reclaim.
  Every verdict line prints **both** samples' operands
  (`api=#41->#41 cpu=1t/1t samples=2`).
- **Verbs unchanged:** the kanban path acts only through `kanban reclaim`, and
  `kanban block` when the churn cap trips. No signal is ever sent to a kanban-worker
  pid — there is no `kill`/`os.kill` in the kanban path. The separate DM-waiter
  reaper (`pgrep -f bot_mode_dm.py`) keeps SIGTERM/SIGKILL, but is its own
  function whose pid source is its own enumeration, never a `task_runs` row.
- **Churn cap unchanged:** `MAX_RECLAIMS=3` / `STATE_WINDOW_H=6`, state in
  `$HOME/.hermes/kanban/.stall_reclaims.json`, written only on a real reclaim (a
  DRY run leaves no file), stale entries pruned.
- **No regressions:** the allowlist (only a pid whose cmdline is a kanban worker
  AND the DB records `running`), the YOUNG/ACTIVE/STALLED threshold matrix, and
  the `tasks:` / `dm:` summary lines are kept.
- **`tests/test_stall_reclaim.py`** — the threshold matrix, the two-consecutive
  verdicts rule, the churn cap, the allowlist, the "no kill reachable from the
  kanban path / a `task_runs` pid can never reach the DM reaper" structure, and
  the negative control.

Not covered (unchanged from the issue): the runtime's own saturation, a real
upstream watchdog, backfilling `max_runtime_seconds`.
