# tick-board-lane-ownership

## Why

The 2026-11-09 board rewrite (issue #2353, measured same day) reassigned 114 kanban cards to
`llgenie-planner` and left 8 running tasks on the wrong lane profile; every tick metric read
"busy" while the fleet was actually idle, because the tick had no line that could see a card was
owned by the wrong lane or a run was executing under a profile that does not own its card. An
ownership defect in board data is invisible to a measurement pass that never reads `assignee`
against `status`.

## What Changes

Give the orchestrator tick (`agents/llgenie-planner/scripts/tick_board.sh`) two measured health
lines, printed every pass, with **no write path to card data** — the tick reports, never repairs:

- **board-ownership invariant**: from `kanban list --json`, print `planner_owned_ready` against a
  plausible ceiling and `lanes_with_ready`; a bulk rewrite of lane-created ready cards to the
  planner goes red, auto-decomposer-created cards count as legitimate.
- **mis-profiled-run counter**: for every `running` task, compare `task_runs.profile` (section D)
  with the task's `assignee`; print the mismatch count.
- **regression guarantee**: a single-card `kanban edit`/`reassign` leaves every OTHER card's
  `assignee` byte-identical and keeps the invariant at zero violations.

## Impact

- Added capabilities: `tick-board-ownership` (specs/tick-board-ownership/spec.md)
- Affected: `agents/llgenie-planner/scripts/tick_board.sh`, `tests/test_tick_board_ownership.py`,
  `tests/test_kanban_single_card_reassign.py`, `tests/test_tick_board.py`, unit-suite fixtures.
- Closes GitHub issue #2353 (PR #2448 carries the implementation this change records).
