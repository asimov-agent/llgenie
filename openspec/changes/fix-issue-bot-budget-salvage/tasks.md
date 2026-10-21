# tasks — fix-issue-bot-budget-salvage

- [x] 1.1 implement step: `timeout-minutes: 90` (job allows 120)
- [x] 1.2 detect + push steps run with `always()`
- [x] 1.3 a step names the budget outcome and what survived
- [x] 1.4 tests: step budget < job, `always()` salvage, named failure
- [x] 1.5 README states the budget
- [x] 1.6 `pytest tests/test_bot_time_budget.py` green
- [x] 1.7 `make test-unit` green
- [x] 1.8 structural gates + `openspec-validate` green, every task ticked
