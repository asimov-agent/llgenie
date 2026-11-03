# 2026-11-03 sync_registry measurement rehydration merge

## What was fixed
- Issue #1649 (red after #1642 merged to main `75f85118`; run `41567928628`, later
  still live at `487ec19d`: hf-live `test_rank_follows_the_given_vram_ram_and_arch`
  asserted `next(... rank_models(new,"cuda",8) if id=="qwen3.8-27b" ...) is not None`
  → failed with `None is not None`).
- Root cause: the #1634/#1636 rehydration that folds the producer's normalized
  `data/measurements.json` back into the per-model `engines` list keyed each run by
  **engine name alone** (`existing.setdefault(e["engine"], e)`). With the producer's
  #689 split, a model row's `engines` was built entirely from measurement runs, so a
  model with many runs of one engine across many cards collapsed to a **single**,
  arbitrarily-first entry — erasing the small-card runs that the picker's
  `card_evidence`/`admitting_measurement`/`fits` (issue #669) use to admit a model on a
  card *or smaller*. Concretely, qwen3.8-27b's 130 runs collapsed to 26 and lost its
  `llama.cpp 14.06 @ 4GB VRAM + 32GB system RAM (partial offload)` and
  `llama.cpp 5 @ RTX 4060 8GB` runs, so `fits(qwen, 8)` was false and the #669 oracle
  ("a tier never places a model `card_evidence` refuses") was — apparently — violated by
  "upstream data". It was not; it was this in-repo merge dropping evidence.
- Fix: `scripts/sync_registry.py::sync()` now keys distinct runs by
  `(engine, hardware)` so every measured card run survives the rehydration. The picker
  sees the full run set and admits qwen at cuda/8 again (`card_evidence="run"`,
  `fits=true`, top engine `llama.cpp`, 123 qwen runs preserved — matching the
  hermetic committed store that never redded).

## Why it was not upstream drift
- The committed `data/models.json` (hermetic twin) always carried all 123 qwen runs
  (including both ≤8GB cuda runs) and the hermetic acceptance passed; only the **live
  re-sync** — which rebuilds the row from measurements.json through the buggy merge —
  lost them. Upstream's `measurements.json` always contained the ≤8GB runs (130 rows).
  The asymmetry was in the in-repo rehydration, not in the producer's store.

## Changed
- `scripts/sync_registry.py` — run key `(engine, hardware)` in the measurements merge.
