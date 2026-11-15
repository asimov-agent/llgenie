# Proposal: mlx-plan-catalog-seam

Issue: #2719. Red lane: ci-hf-live (merge-to-main real-Hub gate), run 43736480220 on `main` (`1dcbf4c3a`):
`tests/test_pick_full_registry.py::test_pick_matrix_llgenie_cli_agrees_with_business_logic`
fails for `lfm2.5-24b-a2b::MLX::metal` and `lfm2-5-24b-a2b::MLX::metal`.

## Why

Two pick seams answer the same question differently. `matrix()` gates each cell through
`pick_quant`, which reads the committed HF class table `data/trending-quant-catalog.json`
(hermetic by design — "llgenie never re-queries the live Hub to decide what a chosen engine
can load on this hardware — it reads this table"). `plan_download()` — the seam `offer()`
and therefore `llgenie --pick` use — resolves `mlx-safetensors` plans against the LIVE Hub.
The table (generated 2026-11-04) records `hermitdave/LFM2.5-24B-A2B-MLX-DWQ-3bit` at
9.7876 GB, which fits the 9.799999 GB weight budget of a 24 GB metal card; the live repo has
since been re-pushed to 9.8835 GB all-files (9.8667 GB safetensors) and fits nowhere. So the
matrix proposes the cell and the CLI refuses it, and the agreement test goes red — a class of
red that any upstream quant re-push can flip in either direction.

## What Changes

- `plan_download()`'s `mlx-safetensors`/`safetensors` branches consult the committed quant
  table first when the model+engine pair is listed in it; the table entry IS the plan (repo,
  files, size, resolve links). The existing live resolution stays as the documented fallback
  for models/engines not yet in the table. This makes the CLI pick and the matrix pick read
  the same decider, as the catalog comment in `scripts/model_engine_pick.py` already promises.
- Hermetic tests: a diverged live recording proves the table's plan wins; a pair absent from
  the table still resolves live; an oversized table plan yields no plan at all; `offer()` and
  `matrix()` agree through the table in both directions.

## Not covered

- The weight-budget policy itself (why a 24 GB metal card gets a 9.80 GB budget) is untouched.
- Resyncing the vendored pair: the live store re-render (trending-local-llms `5680d1c244`)
  removed 34 tracked entries, which the additive-only `make check-registry` gate refuses.
  The store churn is its own linked issue #2722; this change keeps `data/` at main's state
  and makes the seam decide even when the table and the live Hub disagree.

After merge, the next main run of `ci-hf-live` must go green on these two cells; that verdict
belongs to the lane run, not to this change's checklist.
