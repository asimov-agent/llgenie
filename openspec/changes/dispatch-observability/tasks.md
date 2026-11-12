# Tasks: dispatch-observability

- [x] engine-build.yml: add the `producer_run` dispatch input (default empty)
- [x] engine-build.yml: add the "Dispatch provenance" step to the guard job (log + step summary)
- [x] registry-liveness.yml: pass `producer_run=${{ github.run_id }}` on both dispatch shapes
- [x] new text-lock test in tests/test_check_engine_pins_published.py (both sides)
- [x] `make check-workflows` + `make openspec-validate NAME=dispatch-observability` green (rc=0; `make check-dispatch-forms` rc=0 after regenerating the docs/BOTS.md dispatch-forms table for the new input)
- [x] targeted pytest for the touched test modules green (35 passed), then full `make test-unit` green (3687 passed, 13201 deselected)
- [x] changelog fragment + agent-wiki entry naming #2578 and the PR

## Folded-in lane #2583 (tracking issues name their dispatched run)

- [x] registry-liveness.yml: file step records tag→issue into tracking_issues.txt (created number via `--json number`)
- [x] registry-liveness.yml: dispatch step resolves the dispatched queue run into producer.txt (`unknown` when no run appeared)
- [x] registry-liveness.yml: new stamp step comments dispatched run id + shape + producer_run onto each tracking issue
- [x] new text-lock test test_tracking_issues_name_their_dispatched_engine_build_run (all three artifacts)
- [x] gates re-greened (check-workflows, openspec-validate, targeted + full test-unit) and #2583 closed as folded
