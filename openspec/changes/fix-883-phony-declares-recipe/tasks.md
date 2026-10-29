# Tasks

- [x] 1. `scripts/check_wiring.py` asserts the reverse `.PHONY` direction: every key must name a target with a recipe, an inline `;` command, or at least one prerequisite (a declared alias)
- [x] 2. Both failure shapes are errors and are named in one pass — a key with no target, and a target with no recipe and no prerequisite — each with the fix that matches it
- [x] 3. `graph()` exposes `phony_no_target` / `phony_runs_nothing`; `make wiring-report` prints the can-run / no-target / runs-nothing counts
- [x] 4. `tests/test_wiring.py` covers the measured no-target case against real `make` (exit 0, "Nothing to be done"), all offenders in one pass, both alias shapes, and the real tree
- [x] 5. Docs state the rule and the measured failure mode: the `check-wiring` `##` help line + `make help` text, `README.md`, `docs/BOTS.md`, `docs/ARCHITECTURE.md`
- [x] 6. Measured on `main@7e99e199`: zero offenders — the four recipe-less `.PHONY` keys are all declared aliases; recorded in the PR body with the negative control both ways
- [x] 7. `tests/test_wiring.py` passes in `llgenie/test:latest` (16 passed); `make check-wiring`, `check-workflows`, `check-docs`, `lint` and `make openspec-validate NAME=fix-883-phony-declares-recipe` exit 0
