# Tick-board measurement pass: the orchestrator tick is a procedure, not prose (issue #2159)

## What changed

The orchestrator tick's prompt was prose: 13 numbered steps of which only 2
named a runnable command, so a pass could satisfy any step by asserting it.
Measured 2026-11-08: a pass dispatched three lanes onto new backlog issues while
13 of 14 open PRs sat on a stale base and 7 lanes were idle, every step textually
satisfied. Order drifted because it lived in prose ("READ 6a FIRST"), and each
pass re-invented its measurements so two passes were not comparable.

This change makes each pass a procedure:

- **`agents/llgenie-planner/scripts/tick_board.sh`** — one versioned measurement
  command printing fixed sections `A.`–`G.` in order (preflight, open PRs with
  staleness/DIRTY, lanes with idle, queue with every READY task, stalled workers
  both classes, CI at the tip tagged TIP/other by `headSha`, lane drift). A step
  either has a section of that output to act on, or it did not run.
- **`agents/llgenie-planner/cron/llgenie-orchestrator-tick.md`** — the running
  orchestrator prompt captured verbatim (per #2136, the initial commit is the
  real running instruction): every step names its exact command and the line it
  must quote, red PRs and the board-wide stale-base sweep precede backlog, no
  forward references.
- **`make check-tick-prompt`** — host-only divergence gate: reds (exit 1) when
  the live `jobs.json` prompt differs from the versioned copy, naming both byte
  counts; green (exit 0) when they match.
- **`tests/test_tick_board.py`** — hermetic tests (fixture-fed, no network)
  pinning the fixed A–G section order and the 2026-11-08 reproduction
  (`open=14 stale=12 dirty=2`, `idle_non_planner=7`).

The measurement script reads `gh`, `hermes kanban`, and the repo at a freshly
fetched `origin/main` — never a remembered sha (`main` moves roughly every 26
minutes).
