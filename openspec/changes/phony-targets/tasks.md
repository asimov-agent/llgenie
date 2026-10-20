# Tasks

- [x] 1. Declare every undeclared target `.PHONY`: the 22 from the issue plus `generate-requirements-dev-venv` in `tools/Makefile` (found by the new rule)
- [x] 2. `scripts/check_wiring.py`: parse the `.PHONY` blocks (line continuations included) and fail on an undeclared target; refuse a reasonless `not_phony` entry and a stale one
- [x] 3. `tests/test_wiring.py`: the fault (a real file shadows a target, real `make` runs nothing) and the fix, the decision path, and the real tree — in `make test-unit`
- [x] 4. `make wiring-report` prints declared / recorded / undeclared counts
- [x] 5. `README.md` + the AGENTS.md Makefile section document the rule and the report; `agent-wiki/2026-10-20-phony-targets.md` records the work with issue #392 and PR #396
- [x] 6. Verification: `make check-wiring` (184/184 declared, 0 undeclared), `make wiring-report`, `make check-docs`, `make lint`, `make check-workflows`, `make check-secret-output`, `make test-unit` (4838 passed, 3 deselected), `make openspec-validate NAME=phony-targets`
