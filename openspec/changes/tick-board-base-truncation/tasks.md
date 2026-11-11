# Tasks

- [x] 1. `tick_board.sh` section B compares `baseRefOid` against `MAIN` with a prefix rule (either contains the other) instead of `[:8] != main`. Verified: `tests/test_tick_board.py::test_full_length_base_at_a_long_main_is_fresh`, `test_genuinely_stale_base_is_stale_with_its_true_base`
- [x] 2. `tick_board.sh` section F tags `headSha`/main by the same prefix rule. Verified: `tests/test_tick_board.py::test_tip_tag_is_length_robust`
- [x] 3. Existing fixtures unchanged: the #2159 board (8-char main) still reads stale=12 dirty=2; arm classification unchanged. Verified: `tests/test_tick_board.py::test_reproduces_2026_11_08_from_sections_b_and_c`, `tests/test_tick_board_arm.py` (all), `tests/test_tick_board_ownership.py` (all) — 20/20 in llgenie/test at this head
- [x] 4. Docs: `agent-wiki/2026-11-11-tick-board-base-truncation-2450.md` + `docs/changes.d/2026-11-11-tick-board-base-truncation-2450.md` + `make changes-index`, naming issue #2450 and the PR. Verified: `make check-docs` (0 problems at this head)
- [x] 5. `make openspec-validate NAME=tick-board-base-truncation` exits 0 and `make lane-preflight` prints `preflight: OK` at the branch head
