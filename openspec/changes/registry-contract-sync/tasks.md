# Tasks

- [x] 1. `scripts/sync_registry.py` + `data/models.json`: attempted the sync; the new snapshot is lossy, so it is reverted and reported upstream (andyholst/trending-local-llms#463) — the guard is never widened
- [x] 2. `scripts/model_engine_pick.py`: `FOOTPRINT_FIELDS` + `stated_gb` / `stated_context` / `footprint` / `stated_budget_gb`, the measurement's own value winning
- [x] 3. `scripts/model_engine_pick.py`: `fits(model, gb, ram_gb)` honours `system_ram_min`, `trend_list` / `recommend` / `offer` thread the RAM, `rank_engines` rows carry the footprint, `_no_fit_reason` cites the stated floor/weights
- [x] 4. `scripts/registry_keys.py`: `GROW_ONLY_SCALARS` — a lowered `weight_gb` / `context_tokens` / `system_ram_min` (model and measurement) is a finding; grown or restated is not
- [x] 5. `tests/test_registry_footprint.py`: 12 cases for the parsing, the measurement-wins rule, the RAM floor, the engine row, the reason text and the guard
- [x] 6. `README.md` documents the footprint fields and what llgenie does with each; `agent-wiki/2026-10-20-registry-contract-sync.md` records the work with issue #414 and the PR
- [x] 7. Verification: `make test-unit`, `make check-registry`, `make check-registry-keys`, `make check-wiring`, `make check-docs`, `make lint`, `make openspec-validate NAME=registry-contract-sync`
