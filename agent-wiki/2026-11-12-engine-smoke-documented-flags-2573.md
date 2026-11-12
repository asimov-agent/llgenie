# Engine binary smoke probes the documented flags (#2573)

Issue: #2573 · branch: feat/engine-smoke-documented-flags

## What was verified

- **The measured defect.** Fleet run #645 (engine-build.yml run 43206254966, main `e6b9b4b4f`)
  failed `engine-build-mlx-cpu` (job 131144134691, 2026-11-12T11:18:15Z):
  `[smoke] OK … -h` / `[smoke] FAIL … --version: binary exited 2 (usage: mlx_lm.server [-h]
  [--model MODEL] [--adapter-path ADAPTER_PATH])`. `scripts/engine_smoke.py` pinned the probe set
  to `["-h", "--version"]` on both binary-smoke paths and consulted the generated manifest only
  for the `probe: device` skip — while `containers/engines/binaries.json` already documents
  `mlx/cpu → flags ["--help"], probe "help"` (mlx_lm.server is argparse, no `--version`), likewise
  sglang cuda/rocm (`["--help"]`), litert cpu (`["--help"]`), tensorfold cuda (`["--version"]` only).
- **The fix.** Image path probes `engine_image.variant_flags(spec)`; host skill path probes
  `engine_skills.documented_flags(skill, backend)` (per-backend map honored). Empty documentation
  falls back to the pinned `["-h", "--version"]` (issue #2319 default kept); a documented flag
  outside the `{-h, --help, --version}` vocabulary fails closed, naming the engine/variant;
  `probe: device` skip unchanged.
- **Tests.** `tests/test_engine_smoke_binary_flags.py` (8 hermetic tests: per-variant probe sets,
  default, vocabulary fail-closed, device skip, per-backend map, plus a canary against the real
  committed manifest asserting mlx/cpu is `--help`-only) — module green with the adjacent
  `test_engine_binary_flags.py` / `test_engine_smoke_fetch.py`: 25 passed, rc=0 (hermetic TEST_RUN).

## Key decisions

- Issue #2319's pinned pair was re-read as a **bound** (vocabulary + documented-nothing default),
  not a fixed probe set: the gate's stated contract (issue #1717, "the binary answering the flags
  **it documents**") is what the code now enforces. No engine-side hack was made for mlx.

## Current status

- OpenSpec change `engine-smoke-documented-flags` validated; implementation + tests green locally;
  ships as PR #2575 closing #2573. Measured inventory at `151c910ae` (`ALL=1 make
  check-engine-pins-published`, make rc=2): 28 pinned cells, 21 published, 7 unpublished
  (`llama-cpp-laurentzuijdwijk/rocm`, `llama.cpp/cuda`, `llama.cpp/rocm`, `mlx/cpu`,
  `tensorfold/cuda`, `vllm/cuda`, `vllm/rocm`); the collision is proven to red-block only
  `engine-build-mlx-cpu`. It is republished by the next push sweep (#2529 duty), not by this change.
