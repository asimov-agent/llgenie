# Tasks

- [x] 1. `scripts/gen_trending_quant_catalog.py`: `_probe_status()` (ok / gated / dead), `_probe_exists()` keeps "really there", the sync fails only on dead and prints `gated=N` plus the URLs
- [x] 2. `tests/test_quant_generator_edges.py`: the seams move to `_probe_status`, plus the status classifier and the gated-link sync case
- [x] 3. `README.md` notes that a gated file is reported, not fatal; `agent-wiki/2026-10-20-catalog-gated-link.md` records the work with issue #418 and the PR
- [x] 4. Verification: `pytest tests/test_quant_generator_edges.py` (9 passed), `make check-quant-catalog`, `make check-docs`, `make check-wiring`, `make lint`, `make openspec-validate NAME=catalog-gated-link`, `make test-unit`
