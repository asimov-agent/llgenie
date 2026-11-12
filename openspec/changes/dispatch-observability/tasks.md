# Tasks: dispatch-observability

- [x] engine-build.yml: add the `producer_run` dispatch input (default empty)
- [x] engine-build.yml: add the "Dispatch provenance" step to the guard job (log + step summary)
- [x] registry-liveness.yml: pass `producer_run=${{ github.run_id }}` on both dispatch shapes
- [x] new text-lock test in tests/test_check_engine_pins_published.py (both sides)
- [x] `make check-workflows` + `make openspec-validate NAME=dispatch-observability` green (rc=0; `make check-dispatch-forms` rc=0 after regenerating the docs/BOTS.md dispatch-forms table for the new input)
- [x] targeted pytest for the touched test modules green (35 passed), then full `make test-unit` green (3687 passed, 13201 deselected)
- [x] changelog fragment + agent-wiki entry naming #2578 and the PR
