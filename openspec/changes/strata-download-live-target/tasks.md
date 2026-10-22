# Tasks — strata-download-live-target (issue #437)

- [x] 1. OpenSpec change: `proposal.md`, `specs/strata-download-live/spec.md`, this checklist
- [x] 2. `tests/fixtures/unit-suite.json`: `tests/test_strata_download.py` recorded in `excluded` (reason, issue #437, date, target `test-strata-live`)
- [x] 3. `Makefile`: `test-strata-live` runs the whole file in the test image, `.PHONY` + `##` help line
- [x] 4. `tests/test_strata_live_target.py`: the four scenarios above, hermetic
- [x] 5. `README.md` + `agent-wiki/2026-10-22-strata-download-live-target.md` record the boundary and the target
- [x] 6. Verified through the Makefile: `make test-unit` 5014 passed / 6 deselected (exit 0), `make test-strata-live` 30 passed (exit 0), `make lint`, `make check-registry`, `make skills-validate`, `make check-engine-params`, `make check-strata-models`, `make check-wiring`, `make check-docs` exit 0, `make openspec-validate NAME=strata-download-live-target` valid; the guard red with the roster entry removed and green with it; the live file still collects 30 tests and `unit_tests.py list` names it 0 times
