# tasks — fix-rebase-bot-stale-again

- [x] 1.1 drop the early "already rebased today" pass-over; keep the markers for the daily cap
- [x] 1.2 add `skip` / `--skip` so one run never repeats a PR
- [x] 1.3 the loop accumulates `skip` and passes `SKIP=` to `make rebase-bot-sweep`
- [x] 1.4 tests: re-dirtied PR picked, `--skip` respected, loop forwards the list, marker still counts
- [x] 1.5 README states the eligibility rule
- [x] 1.6 `pytest tests/test_rebase_bot_sweep.py` green
- [x] 1.7 `make test-unit` green
- [x] 1.8 `make openspec-validate NAME=fix-rebase-bot-stale-again` exits 0 and every task above is ticked
