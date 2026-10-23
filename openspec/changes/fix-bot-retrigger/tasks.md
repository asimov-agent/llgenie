# Tasks — fix-bot-retrigger (issue #538)

- [x] 1. OpenSpec change: `proposal.md`, `specs/fix-bot-retrigger/spec.md`, this checklist
- [x] 2. `fix-bot.yml`: `workflow_run` on `CI` (failure, pull_request only), resolve the PR with `make auto-merge-resolve`, capture the failed run's log, dispatch that PR; `rounds`/`ATTEMPTS` default 5; new `report_file` input
- [x] 3. `scripts/fix_bot_sweep.py`: `--pr N` (that PR, not the oldest), `--report-file`, `--max-attempts` default 5
- [x] 4. `scripts/fix_loop.sh` + `Makefile`: `FIX_ROUNDS` default 5, `FIX_REPORT_FILE` (repair from the run's log, UNVERIFIED), plumbing
- [x] 5. Tests: sweep `--pr`/rounds=5/workflow trigger, loop UNVERIFIED + default 5 (existing cap tests updated)
- [x] 6. `README.md` + `agent-wiki/2026-10-23-fix-bot-retrigger.md`
- [x] 7. Verified: `pytest tests/test_fix_bot_sweep.py tests/test_fix_loop.py` → 35 passed; `make lint`, `make check-docs`, `make check-wiring`, `make check-workflows`, `make openspec-validate NAME=fix-bot-retrigger`, `make openspec-tasks-check`; `make test-unit` in the PR checks
- [x] 8. PR opened against `asimov-agent/llgenie:main` closing #538