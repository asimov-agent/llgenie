# Tasks

- [x] 1. `make sync-registry` writes the new store: `generated_utc` `2026-11-04T15:29:04Z`, 117 models, 46 engines, contract unchanged (`data/models.json`, `data/trending-README.md`, + measurements/posts/README-link fixtures).
- [x] 2. `make check-registry` is green once the store is committed: the store satisfies the vendored contract, README order matches, and `check-registry-keys` reports additive only (nothing lost vs `HEAD:data/models.json`).
- [x] 3. `make sync-quant-catalog` rewrites `data/trending-quant-catalog.json` + its fixture (93 models / 1796 links) and `make check-quant-catalog` is green.
- [x] 4. `make render-trend-list-matrix` rewrites `tests/fixtures/trend-list-matrix.json` (81 cases) + hub-snapshot and `make check-trend-list-matrix` is green.
- [x] 5. The one engine new to the store (`Surogate`) is decided in `data/unsupported-engines.json` (dated, reasoned from its upstream README, `backend: CUDA`, ship tracked in #1962), `make render-engine-skill-gap` rewrites `data/engine-skill-gap.json` (46 engines, 16 shipped, unresolved 0), and `make check-engine-skill-gap` is green.
- [x] 6. `make skills-validate REGISTRY=data/models.json UNSUPPORTED=data/unsupported-engines.json` is green (16 skills, 46 registry engines, 0 errors).
- [x] 7. `make test-unit` is green (3194 passed) with the goldens re-derived for the new row set.
- [x] 8. `make openspec-validate NAME=registry-sync-2026-11-04` exits 0, and `agent-wiki/` + `CHANGES.md` record the change.
