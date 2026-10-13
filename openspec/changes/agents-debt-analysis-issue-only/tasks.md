# Tasks

- [x] 1. `AGENTS.md` states the rule: analysis surfaces gaps → separate detailed issues, never implementation in the same change
- [x] 2. `tests/test_agents_debt_analysis.py` asserts the rule text is present
- [x] 3. The test is wired into `make test-unit`
- [x] 4. `make lint` passes and `make openspec-validate NAME=agents-debt-analysis-issue-only` exits 0
