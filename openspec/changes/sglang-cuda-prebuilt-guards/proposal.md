# sglang/cuda prebuilt vs the guards that still demand install steps (#1306)

## Why

`#1250` (merged this morning) restored the sglang skill's cuda backend to `prebuilt: true` — the
correct, OOM-safe path (its in-file dated decision: the source AOT `fp8_gemm_kernel.cu` nvcc pass
OOM-kills at every arch set and thread cap). The renderer already turns `prebuilt: true` into ZERO
install steps (`if prebuilt: steps=[]`, engine_skills.py), but the peer guards shipped in the same
merge still demand steps for the cuda backend:

- `skills-validate` (`engine_skills.py::validate`) reports "no install steps for backend cuda"
  whenever an install block is empty — it never shared the renderer's prebuilt special-case.
- `test_sglang_cuda_install_uses_uv_not_pip` asserts `uv pip install ...` is IN the cuda steps,
  which a prebuilt backend legitimately has none of.
- `test_official_upstream_images_are_used_as_bases` asserts `FROM lmsysorg/sglang:v0.5.22` is NOT
  in the cuda Dockerfile — but a prebuilt cell starts exactly FROM that image.
- The source-guard census still counts 1 prebuilt cell; sglang/cuda being restored makes it 2.

Result: `linux/unit` red on `main` — 12 tests fail on the same self-contradiction.

## What changes

1. `scripts/engine_skills.py::validate`: a backend whose container spec is `prebuilt: true` no
   longer fires the "no install steps for backend B" error — the validator and renderer now share
   the same `if prebuilt: steps=[]` special-case.
2. `tests/test_engine_skills.py::test_sglang_cuda_install_uses_uv_not_pip` → retargeted to assert
   BEHAVIOUR: prebuilt → zero steps + validator-clean; source → uv-not-pip. Passes on `main`
   without being weakened into a no-op.
3. `tests/test_engine_skills.py::test_official_upstream_images_are_used_as_bases`: sglang/cuda now
   starts FROM the official image with no install steps; sglang/rocm still compiles.
4. `tests/test_engine_source_guard.py::test_the_census_matches_the_committed_params`: census moves
   to 29 source / 2 prebuilt (sglang/cuda + tensorrt-llm/cuda).

## Impact

- `scripts/engine_skills.py`, `tests/test_engine_skills.py`, `tests/test_engine_source_guard.py`,
  OpenSpec change `openspec/changes/sglang-cuda-prebuilt-guards/`.

## Not covered

- The OOM itself (already a dated decision in the SKILL comment).
- #673 (broader unfrozen-store engine-skill-gap) remains separate.
