# Tasks: fix-mlx-quant-catalog-seam

- [x] 1. `plan_download` mlx/safetensors branch reads the committed quant table: new
      `_catalog_format_plans` (listed, plans) helper and a budget-first largest-fitting
      selection mirroring `engine_supported_quants`.
- [x] 2. Live fallback kept: a (model, engine) pair absent from the table still resolves live.
- [x] 3. Hermetic tests in `tests/test_pick_quant_catalog.py` (3): table-wins-over-diverged-live,
      oversized-table-refuses, unlisted-pair-falls-back — proved red->green against the pre-fix
      code (2 failed on the reverted seam, 3 passed with it).
- [x] 4. Hermetic gates: `python3 scripts/lint_linefeeds.py` OK, `make check-wiring` OK,
      `make check-quant-catalog` OK (generator output unchanged), `make check-docs` OK.
- [x] 5. Real-Hub reproduction of the exact red cell (lfm2.5-24b-a2b/MLX/metal): pre-fix
      matrix offered `hermitdave/...DWQ-3bit` 9.7876 GB while `plan_download`(live) returned
      None (disagree); post-fix both serve the same 9.7876 GB plan (agree).
- [x] 6. OpenSpec change + agent-wiki note + `docs/changes.d` fragment + `pr-body.md`.
