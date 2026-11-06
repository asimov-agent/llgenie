# Tasks

- [x] 1. `openspec/changes/engine-pins-evidence-aware` — proposal + `specs/engine-pins-evidence-aware/spec.md` (G/W/T, a `- **Test:**` line per scenario) + this checklist
- [x] 2. `scripts/check_engine_pins_published.py` — add `_producer_cell_conclusions` (gh read of newest completed engine-build dispatch run's per-engine cell conclusions on a branch)
- [x] 3. `scripts/check_engine_pins_published.py` — evidence-aware pre-poll in `check()` behind `wait_min>0` + repo/branch; red cell => `SKIPPED` recorded decision + return 0 (no wait owed)
- [x] 4. `Makefile` — `check-engine-pins-published` target passes `--repo`/`--branch`
- [x] 5. `.github/workflows/ci.yml` — `engine-pins` job grants `actions: read` and passes `REPO`+`BRANCH`
- [x] 6. `tests/test_check_engine_pins_published.py` — hermetic evidence-aware + wiring tests (red-skip, gate-not-weakened, pre-poll-off, ci wiring)
- [x] 7. Run the check + engine-build sibling suites (11 passed incl live registry test)
