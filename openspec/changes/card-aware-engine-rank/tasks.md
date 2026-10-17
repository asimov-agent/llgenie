# Tasks

- [x] 1. `scripts/model_engine_pick.py`: `_CARD_VRAM` + `measurement_card_gb(hardware)` and `_DATACENTER_HW` + `datacenter_hardware(hardware)`, mirroring trending-local-llms' `hardware_vram_gb` / `_DATACENTER_HW`
- [x] 2. `scripts/model_engine_pick.py`: `rank_engines(model, arch, ids, gb)` ranks 0 proven / 1 bigger card / 2 no card named / 3 other backend / 4 datacenter / 5 no figure, rows carry `card_gb` + `card_class`; the card class applies only on `CARD_ARCHES` hosts
- [x] 3. `scripts/model_engine_pick.py`: `tps_label(e)` is the one t/s text rule; `rank_models`, `recommend` and `matrix` pass their card size into `rank_engines`
- [x] 4. `scripts/llgenie_serve.py`: `_tps_label` delegates to `model_engine_pick.tps_label`
- [x] 5. `tests/test_card_aware_rank.py` (new): the hardware-string table, the datacenter list, proven-vs-bigger, datacenter-vs-consumer, other-backend, the no-card-class path, the labels, the card-aware trend list, and the #225 acceptance case — wired into `make test-unit`
- [x] 6. Existing tests updated for the renumbered ranks and the shared label: `tests/test_trend_pick.py`, `tests/test_model_engine_pick.py`, `tests/test_trend_list_acceptance.py`, `tests/test_registry_sync_trend.py` (its `_same_hw` helper and the October-5 pins)
- [x] 7. `tests/fixtures/trend-list-matrix.json` regenerated with `make render-trend-list-matrix`, and the diff reviewed row by row
- [x] 8. `README.md`: the engine-ranking and t/s-label sections describe the card-aware rule, and `agent-wiki/2026-10-17-card-aware-engine-rank.md` records the change (issue #225, PR)
- [x] 9. Verification: `make lint` green, `make ci-unit` green (4756 passed, `check-trend-list-matrix` OK, `check-registry`/`skills-validate`/`check-wiring`/`check-docs` OK), `make openspec-validate NAME=card-aware-engine-rank` exits 0, and every scenario's `- **Test:**` file/case resolves and passes — plus the GPU-path health proof (the `-cuda` image with `--device nvidia.com/gpu=all` served the 0.5B model, 394.7 tok/s eval)
- [x] 10. PR **#354** opened against upstream `main` with `closes #225` (`https://github.com/asimov-agent/llgenie/pull/354`), from `andyholst:feat/card-aware-engine-rank`, and its CI checks monitored to green
