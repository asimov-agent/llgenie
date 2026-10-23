# Tasks — fix-bot-no-checks (issue #496)

- [x] 1. OpenSpec change: `proposal.md`, `specs/fix-bot-no-checks/spec.md`, this checklist
- [x] 2. `scripts/fix_bot_sweep.py`: `failing_checks()` returns `[]` for the "no checks reported" answer, and still raises on every other `gh` failure
- [x] 3. `tests/test_fix_bot_sweep.py`: the fake `gh` can answer "no checks reported"; one regression case drives the real sweep
- [x] 4. `README.md` + `agent-wiki/2026-10-23-fix-bot-no-checks.md`
- [x] 5. Verified: `pytest tests/test_fix_bot_sweep.py` → 15 passed; `make lint`, `make check-docs`, `make check-wiring`, `make check-workflows`, `make openspec-validate NAME=fix-bot-no-checks`; `make test-unit` in the PR checks
- [x] 6. PR opened against `asimov-agent/llgenie:main` closing #496
