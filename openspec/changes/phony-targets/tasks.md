# Tasks

- [ ] 1. Declare every undeclared target `.PHONY`: the 22 from the issue plus `generate-requirements-dev-venv` in `tools/Makefile` (found by the new rule)
- [ ] 2. `scripts/check_wiring.py`: parse the `.PHONY` blocks (line continuations included) and fail on an undeclared target; refuse a reasonless `not_phony` entry and a stale one
- [ ] 3. `tests/test_wiring.py`: the fault (a real file shadows a target, real `make` runs nothing) and the fix, the decision path, and the real tree — in `make test-unit`
- [ ] 4. `make wiring-report` prints declared / recorded / undeclared counts
- [ ] 5. `README.md` documents the rule and the report; `agent-wiki/2026-10-20-phony-targets.md` records the work with the issue and the PR
- [ ] 6. Verification: `make check-wiring`, `make wiring-report`, `make check-docs`, `make lint`, `make check-workflows`, `make test-unit`, `make openspec-validate NAME=phony-targets`
