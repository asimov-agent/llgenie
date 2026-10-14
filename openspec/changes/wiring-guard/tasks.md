# Tasks

- [x] 1. `scripts/check_wiring.py` builds the real wiring graph (make targets + prerequisites, both makefiles, workflow steps, python imports and run/read paths) and answers: wired at all, and reached by the CI workflows
- [x] 2. `report` names how each document is wired; `check` fails on an unwired document, a non-CI-only document with no decision, a stale decision, a malformed decision, or a workflow calling a missing target
- [x] 3. `tests/fixtures/host-only-wiring.json` records the deliberate host-only documents (Metal-only engines, the installed-launcher health check) with reason, target and date
- [x] 4. Makefile: `check-wiring` + `wiring-report`, in `.PHONY` and the help text; `ci-unit` runs `check-wiring`
- [x] 5. `tests/test_wiring.py` covers the real tree, the report, and each failure mode against real scratch trees (unwired, host-only, stale, malformed, workflow typo); it is named by `make test-unit`
- [x] 6. The live defect is closed: `tests/test_engine_bump_build.py` is deleted and the stale `ci.yml` comment points at `scripts/engine_smoke.py --image`
- [x] 7. README documents the guard, the decisions file and the two targets
- [x] 8. Issue #237 reflects the wiring as implemented; the same audit's dead **target** (`test-install-ci`) is its own issue (#239) and the Nerve/JEV-for-the-implementer question is its own issue (#238)
- [x] 9. In `llgenie/test:latest`: `tests/test_wiring.py` passes and `make check-wiring` exits 0 on the real tree; on the host `make lint` and `make openspec-validate NAME=wiring-guard` exit 0
