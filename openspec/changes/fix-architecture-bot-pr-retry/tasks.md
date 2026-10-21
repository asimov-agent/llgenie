# tasks — fix-architecture-bot-pr-retry

- [x] 1.1 `_gh_retry` retries a transient 502/503/504/timeout on a GitHub write
- [x] 1.2 `publish` adopts an open PR on the branch when the create's answer was lost
- [x] 1.3 a real failure names the issue and branch it created
- [x] 1.4 tests: retry, recovery, real failure
- [x] 1.5 README states the rule
- [x] 1.6 `pytest tests/test_architecture_bot.py` green
- [x] 1.7 `make test-unit` green
- [x] 1.8 structural gates + `openspec-validate` green, every task ticked
