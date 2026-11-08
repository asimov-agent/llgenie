# Make the orchestrator tick a procedure: one measurement command, ordered steps (issue #2159)

## Why

The tick prompt was prose: 13 numbered steps of which only 2 named a runnable
command. A pass could satisfy any step by asserting it ("measured quiescence")
with no output behind the claim — measured 2026-11-08: a pass dispatched three
lanes onto new backlog issues while 13 of 14 PRs sat on stale bases and 7 lanes
were idle, every step textually satisfied. Order drifted because it lived in
prose ("READ 6a FIRST"), and the same measurement was re-invented ad hoc each
pass so two passes were not comparable.

## The change

1. **`tick_board.sh`** — one measurement command printing fixed sections
   `A.`–`G.` in order (preflight, open PRs with staleness/DIRTY, lanes with idle,
   queue with every READY task, stalled workers both classes, CI at the tip
   tagged TIP/other by `headSha`, lane drift command). Versioned under
   `agents/llgenie-planner/scripts/`.
2. **The tick prompt** is a numbered, ordered procedure where every step names
   its exact command and the output line it quotes as evidence; red PRs and the
   board-wide stale-base sweep precede any backlog dispatch; no step refers
   forward. The running `jobs.json` prompt was already rewritten to this shape
   and is captured verbatim under `agents/llgenie-planner/cron/llgenie-orchestrator-tick.md`
   (kept as the initial commit per #2136).
3. **A drift gate** `make check-tick-prompt` reds when the live `jobs.json`
   prompt diverges from the versioned copy — host-only (a CI runner has no live
   jobs.json), mirroring `profile-drift`.
4. Hermetic tests `tests/test_tick_board.py` pin the 2026-11-08 reproduction
   (`stale=12 dirty=2 idle_non_planner=7`) and the fixed A–G section order via
   PR/KANBAN/MAIN fixtures.
