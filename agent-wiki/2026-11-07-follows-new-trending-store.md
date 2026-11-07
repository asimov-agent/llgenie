# llgenie follows the 2026-11-04T15:29:04Z trending store (issue #1961)

## What was verified

- **New store synced**: `make sync-registry` vendored the 2026-11-04T15:29:04Z store into `data/models.json` (117 models, 117 — unchanged; engines 45 → 46). The single new engine is `Surogate` (CUDA, auto-registered).
- **Changed rows**: no models added/removed/renamed; contracts unchanged; one engine added (`Surogate`). The counter re-scrapes and the additive-only LOSSes shown by `check-registry-keys` mid-sync are the transitional comparison (uncommitted new store vs committed old HEAD) — the same 24-loss pattern the prior follow #1681 landed through, and the gate goes green once the store is committed (heads compare new-vs-new). The upstream post removals that last are the #775/#1497-tracked drift, out of scope here.
- **Decision recorded**: `Surogate` → `deferred` in `data/unsupported-engines.json` (dated 2026-11-07, shipped in #1962), so `check-engine-skill-gap` passes on the 46-engine registry.
- **Derived artifacts re-derived**: quant catalog (`data/trending-quant-catalog.json` + fixture, 93 models / 1796 links), trend-list matrix (`tests/fixtures/trend-list-matrix.json`, 81 cases), engine-skill-gap, and the hub-answer fixtures — via `make sync-quant-catalog render-trend-list-matrix render-engine-skill-gap`.

## Gates

`make check-registry check-quant-catalog check-trend-list-matrix check-engine-skill-gap` green; `make skills-validate REGISTRY=data/models.json UNSUPPORTED=data/unsupported-engines.json` green (16 skills, 46 engines, 0 errors); `make test-unit` green (3194 passed) without any test edits — the goldens auto-regen from the new store, and no test asserted a removed row.

## Status

PR opened against `asimov-agent/llgenie:main` from this branch; follows the 2026-11-04 store (issue #1961).
