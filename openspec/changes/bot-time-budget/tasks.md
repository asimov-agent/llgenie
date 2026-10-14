# Tasks

- [x] 1. Write the proposal + spec for the bots' time budget (issues #222/#248).
- [x] 2. Raise the fix job's `timeout-minutes` to fit `FIX_ROUNDS x (check + repair)`, and put
      the measured arithmetic in the workflow header.
- [x] 3. `tests/test_bot_time_budget.py`: a bot job that runs an agent allows >= 60 min, the fix
      job fits its rounds (read from the loop's own default), no step caps below the floor, the
      decision-only jobs keep <= 30 min, and the loop hides no `timeout`.
- [x] 4. Wire the test into the unit list; `make lint`, `make check-wiring`, the OpenSpec
      validator, and the new suite itself.
- [x] 5. Commit as one atomic change, push, open the PR (refs #222, #248).
