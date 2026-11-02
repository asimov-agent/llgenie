# Tasks — arch-census-referent-membership

- [x] 1. `openspec/changes/arch-census-referent-membership` — proposal + `specs/architecture-census/spec.md` (G/W/T, one scenario per requirement) + this checklist, written before any code (done pre-implementation)
- [x] 2. `scripts/check_architecture_census.py` — add the referent-membership check: every `scripts/*.py`/`.sh` name in the §Scripts table (and the parallel BOTS.md sentence) must resolve to a tracked file at the measured sha; subset (named ⊆ tree), never equality; a missing module reddens naming it
- [x] 3. `docs/ARCHITECTURE.md` — drop the dead `engine_matrix_pushed.py` reference from §Scripts (the push-fact gate is now the engine-build producer's matrix/first-fact check, not a standalone script)
- [x] 4. `docs/BOTS.md` — correct the sentence naming `engine_matrix_pushed.py` to state the mechanism without the dead file name
- [x] 5. `tests/test_architecture_census.py` — tests for the referent check: a removed module reddens naming it, a clean tree passes, a subset table passes (negative control + positive cases)
- [x] 6. `docs/changes.d/2026-11-02-arch-census-referent-membership.md` + `agent-wiki/2026-11-02-arch-census-referent-membership.md` + regenerated `CHANGES.md` row (#1123 trio)
- [x] 7. Verified: `make check-architecture-census` exits 1 with the stale reference present (naming `engine_matrix_pushed.py`) and 0 on the corrected tree; `make check-docs`, `make lint`, `make openspec-validate NAME=arch-census-referent-membership` all exit 0
