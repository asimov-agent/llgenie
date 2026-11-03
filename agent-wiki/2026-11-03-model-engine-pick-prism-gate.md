# 2026-11-03 model_engine_pick prism-fork gate

## What was fixed
- Issue #1639 (red-on-main-after-merge at `15450ed1`, run `41560755430`): hf-live
  `test_rank_follows_the_given_vram_ram_and_arch` asserted `35.0 > 43.7` at cuda/16
  because the registry's dense `qwen3.8-27b` row carried a PrismML-fork measurement
  of a *ternary repack* (`quant: PrismML Bonsai 2 27B ternary PQ2_0`, RTX 3060 12GB
  → `measurement_backend CUDA`), and `llama.cpp-prism` has no cuda/rocm image
  (variants `[vulkan, cpu, metal]`), so a **cpu** variant won a cuda row at tps 35.0
  over the genuine cuda `llama.cpp` 96.0 (rank 1, bigger card).
- `scripts/model_engine_pick.py::rank_engines().add()`: made the PrismML-fork gate
  **symmetric** — the fork is only ever the right engine for a model the store marks
  ternary. Existing `if is_ternary(model) and id not in PRISM_ENGINES: return`
  (issue #1092) kept non-prism engines off ternary models; the new
  `if id in PRISM_ENGINES and not is_ternary(model): return` keeps the fork off dense
  models, so its ternary-repack figure can no longer outrank the real card engine.
- Result (verified by executing the code at `15450ed1`): cuda/16 top becomes
  `llama.cpp` 96.0 (cuda) > snapshot 43.7; `llama.cpp-prism` absent from the cuda
  ranking. The #225 improvement assertion is untouched; the 35.0 figure is a
  wrong-arch pick, not a measurement worth re-recording.
- Landed as PR #1642 (bedrock: `474f01d5`).
