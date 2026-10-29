# Tasks

- [x] 1. `make sync-registry` writes the new store: `generated_utc` `2026-10-27T21:47:11Z`, 112 models, 43 engines, contract unchanged (`data/models.json`, `data/trending-README.md`).
- [x] 2. `make check-registry` is green: the store satisfies the vendored contract, README order matches, and `check-registry-keys` reports additive only (nothing lost vs `HEAD:data/models.json`).
- [x] 3. `make sync-quant-catalog` rewrites `data/trending-quant-catalog.json` + its fixture (89 models / 1661 links) and `make check-quant-catalog` is green.
- [x] 4. `make render-trend-list-matrix` rewrites `tests/fixtures/trend-list-matrix.json` (81 cases) and `make check-trend-list-matrix` is green.
- [x] 5. The one engine new to the store (`Rapid-MLX`) is decided in `data/unsupported-engines.json` (dated, reasoned from its upstream README, `backend: Metal`), `make render-engine-skill-gap` rewrites `data/engine-skill-gap.json` (43 engines, 16 shipped, unresolved 0), and `make check-engine-skill-gap` is green.
- [x] 6. `make skills-validate REGISTRY=data/models.json UNSUPPORTED=data/unsupported-engines.json` is green (16 skills, 43 registry engines, 0 errors).
- [x] 7. `make test-unit` is green with the goldens re-derived for the new row set.
- [x] 8. `make openspec-validate NAME=registry-sync-2026-10-27` exits 0, and `agent-wiki/` + `CHANGES.md` record the change.
