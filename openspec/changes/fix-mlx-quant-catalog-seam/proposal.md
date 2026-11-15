# Proposal: fix-mlx-quant-catalog-seam

## Why

Issue #2719. Measured on `main` `1dcbf4c3ae` (run 43736480220, the ci-hf-live
merge-to-main `make test-unit-network` lane): `matrix()` offers the
`lfm2.5-24b-a2b::MLX::metal` cell because the committed quant table
(`data/trending-quant-catalog.json`, generated 2026-11-04) records
`hermitdave/LFM2.5-24B-A2B-MLX-DWQ-3bit` at 9.7876 GB, which fits the 9.80 GB weight
budget of a 24 GB metal card; `llgenie --pick --engine MLX --dry` refuses because
`plan_download()` (`scripts/model_engine_pick.py`) resolves MLX repos against the LIVE
Hub, where the same repo has since been re-pushed to 9.8835 GB (9.8667 GB safetensors) —
no MLX repo of the model fits. Two seams, two answers, from the same model+card.

## What Changes

- `plan_download`'s mlx-safetensors/safetensors branch reads the committed HF class table
  (`quant_catalog` → a new `_catalog_format_plans` helper) when the (model, engine) pair is
  listed: it serves the SAME budget-fitting snapshot `engine_supported_quants`/`_matrix_plan`
  serve, so `llgenie --pick` and `matrix()` answer the same question through the same
  committed seam. The table's own sizes are the answer — an upstream repo re-push (a live
  figure that no longer fits) cannot flip a certified-green pick red.
- A (model, engine) pair the table does NOT list still resolves live — the documented
  fallback is kept unchanged.
- Selection is budget-first then largest-fitting, mirroring `engine_supported_quants`'s
  `_add` (filter to budget, then dedup by repo+files), so the two surfaces agree even when
  the table happens to carry a duplicate plan size.

## Impact

- Affected specs: `plan-download` (ADDED requirement: a catalogued mlx/safetensors pair
  resolves from the committed table; an unlisted pair falls back to live).
- Affected code: `scripts/model_engine_pick.py` (`plan_download` mlx/safetensors branch,
  new `_catalog_format_plans`); new `tests/test_pick_quant_catalog.py` (3 hermetic tests).
- Out of scope (separate linked issue): the generator's `carry_over` re-inserts a re-pushed
  repo at a STALE size beside its fresh live size (a duplicate same-repo plan); the weekly
  sync should update the size, not add a twin. Observed 2026-11-15 while attempting
  `make sync-quant-catalog` for the AC3 resync; deferred so this change stays one objective.
- After merge, the ci-hf-live lane's `make test-unit-network` verifies the full agreement
  set against the real Hub on the 24 GB metal card.
