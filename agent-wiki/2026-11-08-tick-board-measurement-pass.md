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
  real running instruction): a strict **`STEP 1 … STEP 13`** sequence, every step
  naming its exact command and the line it must quote (`Quote:` per step), red
  PRs and the board-wide stale-base sweep precede backlog, and no step refers
  forward ("read step X first" is gone). **STEP 6 — HOW TO DELEGATE** makes a
  dispatch concrete: a brief written to a file, the single `delegate.sh` command
  (`$DG --lane --issue --brief --message`) that validates the brief / refuses a
  second vehicle / creates the task / dispatches / reads the board back, the
  three-state confirmation (`running` / `ready (queued on capacity, spawned=0)` /
  `BLOCKED`), the always-`--message` rule (task + message = ONE assignment), and
  the `BOT <lane> · #<id> · <task-id> · <status>` report line. STEP 4 (already in
  the live prompt) carries the red-PR priority incl. ARM-only-green (4e),
  unarmed-and-not-green (4f) and one-check-many-PRs (4g).
- **`make check-tick-prompt`** — divergence gate (`scripts/check_tick_prompt.py`):
  reds (exit 1) when the live `jobs.json` prompt differs from the versioned copy,
  naming both byte counts; green (exit 0) when they match. Runs on any host with
  the live profile; a CI runner has no live jobs.json so the comparison target is
  the human/planner host.
- **`tests/test_tick_board.py`** — hermetic tests (fixture-fed, no network)
  pinning the fixed A–G section order and the 2026-11-08 reproduction
  (`open=14 stale=12 dirty=2`, `idle_non_planner=7`).
- **`tests/test_check_tick_prompt.py`** — hermetic drift-gate tests: green on
  match (including the trailing-newline normalization), red on divergence with
  both byte counts named, exit 2 on a missing job.

The measurement script reads `gh`, `hermes kanban`, and the repo at a freshly
fetched `origin/main` — never a remembered sha (`main` moves roughly every 26
minutes). The versioned prompt equals the live `jobs.json` prompt byte-for-byte
(gate green at `main` 7ef346c8); the planner applies the live copy, this
repository carries the reviewable text.
