# tasks — fix-rebase-bot-real-gates

- [x] 1.1 `scripts/rebase_bot.sh`: gates chained with `&&`
- [x] 1.2 `.github/workflows/rebase-bot.yml`: provide the test image (`make test-image`) before the drain step
- [x] 1.3 tests: failing gate blocks the push; default chain + image step
- [x] 1.4 README states the rule
- [x] 1.5 `pytest tests/test_rebase_bot_sweep.py` green
- [x] 1.6 `make test-unit` green
- [x] 1.7 structural gates + `openspec-validate` green, every task ticked
