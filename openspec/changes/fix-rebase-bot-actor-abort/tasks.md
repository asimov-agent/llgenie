# tasks — fix-rebase-bot-actor-abort

- [x] 1.1 `scripts/rebase_bot.sh` aborts its stopped rebase on every failure path
- [x] 1.2 the failing-agent test asserts no stopped-rebase state remains
- [x] 1.3 README states the rule
- [x] 1.4 `pytest tests/test_rebase_bot_sweep.py` green
- [x] 1.5 `make test-unit` green
- [x] 1.6 `make openspec-validate NAME=fix-rebase-bot-actor-abort` exits 0 and every task above is ticked
