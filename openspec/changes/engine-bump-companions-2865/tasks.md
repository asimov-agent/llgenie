# Tasks

- [x] 1. `_rewrite_pin_asserts`: skip `docs/changes.d/` rows; rewrite current-pin lines in the bumped engine's SKILL.md
- [x] 2. Rewrite frozen image-hash/tag literals in `tests/` after regen moves a variant hash (bumped engine only)
- [x] 3. `bump()` generates the `agent-wiki/` + `docs/changes.d/` note pair; `.github/workflows/engine-bump.yml` stages `agent-wiki/`
- [x] 4. Bump PR body template carries `OPENSPEC: publish-changed-pin-images`
- [x] 5. `tests/test_ci_publish_order.py` case 2 branches on `retagged_engine_ids`
- [x] 6. New `tests/test_engine_bump_companions.py`; update `tests/test_engine_bump_pr_body.py` expectations
- [x] 7. This change's own note pair (`agent-wiki/` + `docs/changes.d/` row) and `make changes-index`
- [x] 8. Gates green: targeted pytest, `make lint`, `make check-workflows`, `make check-wiring`, `make check-docs`, `make openspec-validate NAME=engine-bump-companions-2865`, full `make test-unit`, `make lane-preflight`
- [x] 9. Push branch, open PR `closes #2865` with body mirroring the issue ACs; sync the issue body to this change
