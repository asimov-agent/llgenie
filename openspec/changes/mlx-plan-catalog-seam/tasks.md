# Tasks: mlx-plan-catalog-seam

- [x] Route `plan_download`'s mlx-safetensors/safetensors branches through the committed quant table when the model+engine pair is listed; live resolution stays the fallback for unlisted pairs
- [x] Hermetic tests: table wins over a diverged live recording; unlisted pair still resolves live; nothing-fits yields no plan
- [x] `offer()`/CLI `--pick --engine MLX --dry` and `matrix()` agree on the catalog seam (agreement invariant proven hermetically for the lfm2.5 row with a fixture table)
- [x] Vendored pair kept at main's state (resync out of scope — store churn filed as #2722; `make check-registry`/`make check-quant-catalog` green on main's data)
- [x] `make lint`, `make check-registry`, `make check-quant-catalog`, `make check-wiring` green
- [x] The hermetic drift/data modules green on main's vendored data (`test_engine_skill_gap`, `test_hub_snapshot`, `test_trend_list_matrix`, `test_pick_quant_catalog`, `test_network_marker`)
- [x] The network pick suite green locally against the real Hub for the pick-agreement set (`pytest tests/test_pick_full_registry.py -m network`, 12384 passed, rc=0)
- [x] `make openspec-validate NAME=mlx-plan-catalog-seam` passes; the full `make test-unit` + `make lane-preflight` verdict is recorded in the PR (verification proof, not a work step)
