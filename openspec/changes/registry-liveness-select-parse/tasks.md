# Tasks

- [x] 1. `.github/workflows/registry-liveness.yml` — the dispatch read loop binds the `[select]` marker in its own first field (`while read -r sel engine variant tag`) and skips loudly any line whose first field is not exactly `[select]` or which lacks the four cell fields, so the engine id (dots intact), variant and tag suffix reach `engine-build` un-shifted
- [x] 2. Falsified: the new guard test fails on the pre-fix 3-variable `while read -r engine variant tag` read loop (it would bind the literal `[select]` as the engine) and passes on the fixed 4-field guarded loop
- [x] 3. `tests/test_check_engine_pins_published.py` — `test_the_liveness_dispatch_reads_all_four_select_fields` locks the workflow's read field count/binding to the gate's 4-field `[select]` line so the two cannot drift
- [x] 4. The 22 malformed runs named in #2567 are documented as no-ops in the issue and no correct dispatch is duplicated by the fix (each still-missing cell is re-dispatched once by the next `registry-liveness` run with correct inputs)
- [x] 5. `agent-wiki/2026-11-12-registry-liveness-select-parse.md` records the change, naming issue #2567; `CHANGES.md` gains the matching index row
- [x] 6. `make test-unit`, `make lint`, `make check-wiring`, `make check-docs` and `make openspec-validate NAME=registry-liveness-select-parse` all pass
