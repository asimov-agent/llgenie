# stall_reclaim log axis samples the lane agent.log + API-call delta over two consecutive verdicts (issue #2155)

## What changed

The orchestrator tick's stall detector no longer reads the per-run kanban log for its log axis. The
previous `stall_reclaim.sh` read `log_age_m` from `$KANBAN_HOME/kanban/logs/<task>.log`, which receives
only the spawn session header — measured 2026-11-09, `kanbanlog == age` on 8/8 running tasks while every
lane `agent.log` was 0.1–1.8 min old with a rising `API call #N` counter. A DRY run flagged LIVE worker
`t_959810c9` (agent.log 0.3 min old, `API call #44`) STALLED; `--apply` on that verdict would have
reclaimed a working lane and the `cap=3/6h` then blocked genuine reclaims. The `cpu` axis is also
uninformative: a model-API-blocked worker accrues ~1 tick per sample window, so `cpu <= MAX_CPU_TICKS`
holds for every healthy worker.

The fix ports the sweep to `agents/llgenie-planner/scripts/stall_reclaim.py` and changes the log axis to
the lane session log plus the API-call counter. For each candidate task the lane comes from
`task_runs.profile`; the signals are `$HOME/.hermes/profiles/<lane>/logs/agent.log`'s mtime and the last
`API call #<N>` in that file. Each verdict is taken from **two samples ≥ 60 s apart**; a task is `ACTIVE`
when EITHER the agent.log mtime advanced across the samples OR the API counter rose, and `STALLED` only
when both are stale and CPU is idle. **Two consecutive STALLED verdicts** are required before any reclaim;
a single sample never triggers action. Every verdict line prints both samples' operands
(`api=#41->#41 cpu=1t/1t samples=2`). The kanban path acts only through `kanban reclaim`, and
`kanban block` when the churn cap trips — no signal is ever sent to a worker pid; the separate DM-waiter
reaper (`pgrep -f bot_mode_dm.py`) keeps SIGTERM/SIGKILL but is its own function whose pid source is its
own pgrep enumeration, never a `task_runs` row. Churn cap unchanged (`MAX_RECLAIMS=3`/`STATE_WINDOW_H=6`),
state written only on a real reclaim (a DRY run leaves no file), stale entries pruned.

## Verified against the spec

- live worker with fresh lane `agent.log` but old kanban log -> ACTIVE
- worker with stale `agent.log` and unchanged API counter across two samples -> STALLED
- worker with stale `agent.log` mtime but advancing API counter -> ACTIVE
- single-sample STALLED -> no reclaim action
- no `kill`/signal reachable from the kanban path; a `task_runs` pid can never reach the DM reaper
- `agents/llgenie-planner/scripts/stall_reclaim.py` + `tests/test_stall_reclaim.py` + the OpenSpec change
  `openspec/changes/stall-reclaim-log-axis/` (proposal + G/W/T spec with a `- **Test:**` line per scenario)

## Status

Committed on `fix/2155-stall-reclaim` as PR #2364. Gates: regexp matrix + two-consecutive-verdicts +
operands-printed + no-kill-in-kanban-path locked by `tests/test_stall_reclaim.py`.
