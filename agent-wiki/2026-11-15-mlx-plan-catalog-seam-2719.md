# 2026-11-15 — mlx whole-repo pick plans answer from the catalog (issue #2719)

OpenSpec change: `mlx-plan-catalog-seam`. Branch `feat/ci-hf-live-mlx-plan`, PR opened against
upstream main closing issue #2719.

## Verified against the spec

- `scripts/model_engine_pick.py::_catalog_whole_repo_plan()` answers catalogued
  mlx-safetensors/safetensors pairs from `data/trending-quant-catalog.json`; `plan_download`
  and `pick_quant` consult it before the live Hub, matching the ADDED requirements in
  `openspec/changes/mlx-plan-catalog-seam/specs/mlx-plan-catalog-seam/spec.md`.
- Measured defect (ci-hf-live run 43736480220, job 132884996593): `lfm2.5-24b-a2b::MLX::metal`
  — matrix proposed DWQ-3bit (9.7876 GB, budget 9.80 GB) from the catalog while the live
  `hermitdave/LFM2.5-24B-A2B-MLX-DWQ-3bit` had been re-pushed to 9.8835 GB; the CLI refused
  what the matrix offered.
- Local proofs (no GitHub pipeline started for verification):
  `pytest tests/test_pick_quant_catalog.py` 4 passed (table-wins, no-fit-no-plan,
  uncatalogued-live-fallback, offer/matrix agreement);
  `pytest tests/test_pick_full_registry.py -m network` 12384 passed rc=0 against the live Hub
  on main's vendored pair; `make check-registry check-quant-catalog lint check-wiring
  openspec-validate` all rc=0.

## Key decisions

- Resyncing the vendored pair is OUT of scope: the live store re-render
  (trending-local-llms `5680d1c244`) removed 34 tracked entries, which the additive-only
  registry gate refuses to absorb — that churn is its own issue #2722. The seam makes matrix
  and CLI agree without rewriting `data/`.
- Multi-part (strata/tensorfold) plans are excluded from the seam; only whole-repo formats
  have a catalog size claim.
- The network-marker purity fix (`tests/test_pick_quant_catalog.py::_use_recording` sets
  `mp.HUB_SNAPSHOT_ENV` directly) keeps `make test-unit`'s
  `test_no_unmarked_remote_fetch_enters_the_gate` green — purity propagates only through
  helper bodies that name the substitute env var.

## Current status

Seam implemented, hermetic + network pick suites green locally, docs landed; unit-suite verdict
recorded in the PR. PR drives CI to green + auto-merge; the next `ci-hf-live` main run carries
the lane verdict.
