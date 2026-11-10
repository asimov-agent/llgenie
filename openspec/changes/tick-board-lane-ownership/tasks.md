# Tasks

- [x] 1. `tick_board.sh` prints the board-ownership invariant line every pass from `kanban list --json`, no write path. Verified: `tests/test_tick_board_ownership.py::test_healthy_board_reports_ok_within_planner_domain`, `test_ownership_line_prints_even_with_empty_board` (module proven by CI `ci-unit` at the PR #2448 head)
- [x] 2. Bulk-rewrite detection: lane-created ready cards rewritten to the planner report violations; auto-decomposer-created cards stay legitimate. Verified: `test_rewriting_a_lane_created_ready_card_to_planner_goes_red`, `test_planner_domain_counts_auto_decomposer_created_as_legitimate`
- [x] 3. Mis-profiled-run counter compares `task_runs.profile` with the card `assignee` for every running task. Verified: `test_six_misprofiled_runs_report_six`, `test_healthy_running_board_reports_zero_mismatch`
- [x] 4. Single-card edit regression: other assignees byte-identical, invariant at zero. Verified: `tests/test_kanban_single_card_reassign.py` and `test_single_card_edit_leaves_other_assignees_unchanged_and_zero_violations`
- [x] 5. New test modules wired into the unit-suite fixtures (`tests/fixtures/unit-suite.json`, `host-only-wiring.json`). Verified: `make check-wiring` at the PR head in CI (the wiring guard runs in `ci-unit`)
- [x] 6. Docs note + `docs/changes.d` index row naming #2353 and PR #2448 exist on the branch. Verified: `agent-wiki/2026-11-10-tick-board-ownership-2353.md` + `docs/changes.d/2026-11-10-tick-board-ownership-2353.md` present at the head
