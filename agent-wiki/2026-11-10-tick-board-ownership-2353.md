# The tick measures board ownership and mis-profiling instead of trusting its view of the board (issue #2353)

The 2026-11-09 board rewrite (114 cards reassigned to `llgenie-planner`, 8 mis-profiled workers) left the
fleet idle while every metric read "busy": the tick trusted its own `kanban list` view of who owned what,
and that view said the planner domain was empty so nothing it could report was wrong. Measured state,
not belief, is the gate — so the tick now prints two measurable invariants every pass, reading
`kanban list --json` (`assignee`, `status`) with no new dependency:

- a `board-ownership` line naming `planner_owned_ready=N` against the planner-domain ready ceiling and
  `lanes_with_ready=N` -> `OK`/`RED`;
- a `profiled_mismatch=N` counter per `running` task (task `assignee` vs `task_runs.profile`).

Example (the live board, read-only scan, `rc=0`):

```
board-ownership: planner_owned_ready=0 (expect <= planner-domain 0 (ready, planner/decomposer-created)) lanes_with_ready=0 -> OK
profiled_mismatch=0
```

The 2026-11-09 case would have printed `profiled_mismatch=6`.

## Proof that the guard catches the bug

The AC3 write-path guarantee — a single-card `kanban edit`/`reassign` leaves every other card's `assignee`
byte-identical — and the AC4 negative control are proven with the REAL hermes kanban CLI against a
throwaway `HERMES_KANBAN_DB` (`make test-board-ownership-host`, host-only by design: a CI runner has no live
board to mutate and no hermes in the hermetic image). Stubbing the invariant off line 192 made AC1
redden loudly (`test_rewriting_a_lane_created_ready_card_to_planner_goes_red`). The hermetic gate runs
`tests/test_tick_board_ownership.py` (`scripts/unit_tests.py`); the write-path proof is wired host-only via
`unit-suite.json` + `host-only-wiring.json` (`make test-board-ownership-host`).

## Not covered

None — all four #2353 acceptance criteria are implemented and tester-verified PASS at the pushed head.
The issue-side `acceptance-unchecked` box is the reviewer's verdict write-back (`acceptance_writeback`,
#1644), not an author action.
