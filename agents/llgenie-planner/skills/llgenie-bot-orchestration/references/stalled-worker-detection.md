# Stalled workers: how to tell a corpse from a busy lane

A kanban worker can be **alive-but-idle indefinitely** while the board reports it
`running`. Nothing in the runtime detects it, and every field that looks like a
liveness signal is useless. Measured 2026-11-08: four workers, log-age
159/110/88/50 min, all 0.1% CPU, two having written no output at all, holding
every queue slot so `kanban dispatch` could place no work.

## Five signals that DO NOT work (all measured — do not build on them)

- **`last_heartbeat_at`** — read **0 minutes old** for a worker idle 2.5 h. The
  heartbeat is a timer, not a work signal. It is the most misleading field on
  the board, because it makes a corpse look fresh.
- **`state.db` mtime** — a fresh mtime reads as "the lane is busy, not stuck"
  and it is wrong for the same reason: the heartbeat write touches the DB every
  minute whether or not any work exists. Measured 2026-11-08: `state.db` mtime
  1 min old while **all three** of that lane's workers sat at log-age 44/42/30
  min with ~0 CPU. If you check the DB to decide liveness you will conclude the
  opposite of the truth. Liveness is log mtime, always.
- **`max_runtime_seconds`** — a real column, but the runtime only **prints** its
  value into the worker's prompt (`"Max runtime: Ns"`). Nothing enforces it.
  Setting it stops nothing.
- **task status `running`** — true whenever the pid is alive.
- **wall-clock age alone** — a legitimately long build is indistinguishable.

`kanban gc` is log retention and `kanban repair` is `PRAGMA integrity_check`;
neither touches a stalled worker. There is no built-in stall killer.

## What to measure instead

Three independent, cheap facts, and STALLED requires all three:

1. **log growth** — mtime age of `<kanban>/logs/<task>.log`, the only place real
   output lands.
2. **CPU delta** — `utime+stime` from `/proc/<pid>/stat` sampled twice; a worker
   blocked in `ep_poll` on an unserved socket accrues ~0 ticks.
3. **process age** — from `started_at`, so a fresh worker is never a candidate.

Mapping task → pid comes from the DB, not the CLI: the JSON output has no `pid`.

```bash
sqlite3 -separator '|' "$HOME/.hermes/kanban.db" \
  "SELECT task_id, worker_pid, started_at FROM task_runs
   WHERE status='running' AND worker_pid IS NOT NULL;"
```

## `kanban reclaim` IS the kill — never signal a pid yourself

A version that sent `SIGTERM` to worker pids was refused by the gateway
lifecycle guard. The guard is right: SIGTERM from inside the gateway's own
process tree propagates, and it cannot tell your target from its parent.

Rewritten to call only the supported API, and measured:

```
before : pid 947866  STAT Ssl  etimes 9710  %CPU 0.1
reclaim: Reclaimed t_bcf39cc7
after  : pid gone    task status = ready
```

`kanban reclaim` frees the slot **and** terminates the worker as a side effect.
It is the whole fix, and it is safe to run inside the tick.

## A churn cap is mandatory, not defensive

Reclaiming frees the slot and the dispatcher **immediately re-runs the task** —
measured: all four reclaimed tasks came back within seconds with fresh pids.
A task that stalls for a structural reason (a saturated runtime, a task that
cannot complete) would be reclaimed, re-run and re-stalled forever, and the loop
would hide its own cause.

After `MAX_RECLAIMS` (3) in `STATE_WINDOW_H` (6 h), `kanban block` the task with
the measured evidence instead of recycling it. Note `kanban block` takes the
reason as a **positional** argument, not `--reason`.

## Two stall classes — a sweep that reads only one will lie to you

Reading `task_runs` finds kanban workers and nothing else, so a pass can report
`stalled=0` while orphaned helpers sit idle forever. Measured 2026-11-08: five
`bot_mode_dm.py` waiters at ~30 min, `__futex_wait`/`hrtimer_nanosleep`, **none
carrying a timeout or bound flag** — the same failure shape as a stalled worker,
and nothing reaps them either.

| | kanban workers | DM delivery waiters |
|---|---|---|
| found by | `task_runs` + `worker_pid` | `pgrep -f bot_mode_dm.py` |
| threshold | `STALL_MIN` (20 m) | `DM_STALL_MIN` (30 m) |
| evidence | log mtime + CPU Δ + age | age + CPU Δ + **no timeout flag** |
| action | `kanban reclaim` / `kanban block` | SIGTERM, then SIGKILL |

`kanban reclaim` does not apply to a DM waiter — it is not a task. Report both
lines separately (`tasks: …` / `dm: …`) so a reader cannot mistake an empty task
queue for a healthy host.

## One stuck worker or a saturated runtime? Reclaim buys a window, not capacity

Before reclaiming in a loop, answer which of two very different failures you
are looking at:

- **one task is stuck** — its siblings are producing output, the rate is normal.
  Reclaim it; done.
- **the runtime is saturated** — every lane's turns stall within ~30 min of
  starting, and the *same* tasks come back and stall again. Reclaiming here is a
  treadmill: it wins a working window, then the congestion re-stalls the same
  turns.

Measure the runtime, not just the tasks. A single gateway process serves every
concurrent lane turn, and when it is pegged its API socket stops being served —
which is exactly the `ep_poll` stall the worker shows.

```bash
ps -o pid,etime,%cpu,rss --no-headers -p <gateway-pid>
awk '/^Threads/{print $2}' /proc/<gateway-pid>/status   # thread count
# ticks of CPU burned over 4s (utime+stime delta): hundreds = pegged
```

Measured 2026-11-08: gateway at **97.2 % CPU, 388 threads, 81 established
connections** while eight lane turns were queued; reclaiming freed six slots and
the dispatcher re-spawned the same tasks, which were back to `stalled≈6` inside
half an hour. Report that as a **capacity finding for the owner** (fewer
concurrent turns / a second gateway / a faster model), not as "fixed" — and do
not present a reclaim round that will be undone in 30 min as a cure. Keep the
churn cap doing its job, and say plainly that the sweep is managing the symptom
of a ceiling you cannot raise from inside a lane.

## Reporting

A pass must distinguish "busy" from "occupied by a corpse". Quote the sweep's
summary line (`stalled= active= young= orphan= reclaimed= blocked=`) so the
next reader sees the measurement rather than an adjective.

A worker whose log ends in `[kanban-worker-exit] rc=1` is a **failed** task still
holding a slot — the worst case, because it can never produce output again.
