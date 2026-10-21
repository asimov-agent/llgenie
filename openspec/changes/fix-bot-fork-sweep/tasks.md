# tasks — fix-bot-fork-sweep

- [x] 1.1 `fix_bot_sweep.py`: `--own-fork`, eligibility accepts the allowlisted fork
- [x] 1.2 `Makefile`: `fix-bot-sweep` forwards `OWN_FORK=`
- [x] 1.3 `fix-bot.yml`: sweep passes `OWN_FORK=andyholst`; resolve the head repo, fetch/checkout from it, push to `REMOTE`
- [x] 1.4 tests: allowlisted fork chosen, other fork skipped, push targets the head remote
- [x] 1.5 README states the fork rule
- [x] 1.6 `pytest tests/test_fix_bot_sweep.py` green
- [x] 1.7 `make test-unit` green
- [x] 1.8 structural gates + `openspec-validate` green, every task ticked
