# Tasks — quant-catalog-order-737

- [x] `scripts/gen_trending_quant_catalog.py::_model_catalog` sorts each cell's deduped plan
      list by `(size_gb, repo, path)` ascending before writing the cell.
- [x] `compare()` turns the same-set-different-order case into a FAILURE naming the cell
      (replacing the reorder NOTE), keeping every other note/failure rule intact.
- [x] Flip the scenario test: `test_a_reordered_regeneration_is_a_note_not_a_failure` →
      `test_a_reordered_cell_is_a_failure_once_generation_is_reproducible` (assert exit-1
      failure naming the cell).
- [x] New determinism tests: shuffled Hub candidates produce the identical cell
      (`tests/test_quant_generator_edges.py`), and two replays of the recorded snapshot
      answers produce byte-identical payloads (`tests/test_trending_quant_catalog.py`).
- [x] Consumer rule test: `engine_supported_quants` returns ascending size whatever order
      the committed row lists (`tests/test_pick_quant_catalog.py`).
- [x] Carry-over order test: a kept plan re-inserted by `carry_over()` lands in the cell's
      repository order (`tests/test_quant_catalog_compare.py`).
- [x] Regenerate the committed table + Hub snapshot under the new rule through the existing
      seam (`make sync-quant-catalog`): 93 models, 2139 links, 0 cells out of the new order;
      the diff vs the previous table is order-only apart from the drift the sync announces
      (2 plans dropped on dead 404 links, 12 newly published conversions recorded).
- [x] `agent-wiki/2026-11-20-quant-catalog-order-737.md` + `docs/changes.d/` fragment +
      `make changes-index`.
- [x] Final pre-push proofs: `make check-quant-catalog` rc=0; targeted batteries
      (`test_trending_quant_catalog`, `test_quant_catalog_compare`,
      `test_quant_generator_edges`, `test_pick_quant_catalog`, `test_engine_supported_quants`)
      rc=0; `make openspec-validate NAME=quant-catalog-order-737` rc=0;
      `make lane-preflight` prints `preflight: OK`.

Ship action (outside this checklist): push the branch, open the closing PR, drive it green.
