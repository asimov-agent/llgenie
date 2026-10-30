# vLLM's three cells build from the pinned source, not the PyPI wheel (#937)

## Why

`vllm` has three container cells (`cuda`, `rocm`, `cpu`), and all three say `prebuilt: true` and
install the engine from PyPI — the cuda cell `uv pip install vllm=={version} --torch-backend=…`,
the rocm cell from the AMD wheel index, the cpu cell the `+cpu` release wheel. Nothing in this
repository compiles vLLM or its kernels, so a CUDA/torch skew in the shared base is invisible to
three quarters of the matrix. The sglang rocm cell (#938's subject) already clones and builds from
source — this change ports that recipe shape to vLLM's three cells.

## What changes

1. `skills/engines/vllm/SKILL.md`: drop `prebuilt: true` on `container.{cuda,rocm,cpu}` and give
   each `install.*` the clone-and-build shape — clone `vllm-project/vllm` at `pinned:`, then
   `uv pip install --no-build-isolation -e .` with the backend's target env
   (`VLLM_TARGET_DEVICE=cuda|rocm|cpu`). The compiler arch lists come from the shared fat lists via
   new `hw_flags` keys: `CMAKE_CUDA_ARCHITECTURES` (cuda) and `PYTORCH_ROCM_ARCH` (rocm).
2. Build on the shared devel base per backend, adding only `python3-dev`. `container` blocks no
   longer start `FROM vllm/vllm-openai*`.
3. `make generate-engine-params ENGINE=vllm`; commit the regenerated `params/vllm.json` and the
   three `Dockerfile.{cuda,rocm,cpu}`.
4. Move the source-guard census and the official-base test with the change.

## Impact

- `skills/engines/vllm/SKILL.md`, `containers/engines/params/vllm.json`,
  `containers/engines/dockerfiles/vllm/Dockerfile.{cuda,rocm,cpu}`.
- `tests/test_engine_source_guard.py` (census: 25 source / 6 prebuilt on this branch — sglang/cuda
  stays prebuilt, that is #938), `tests/test_engine_skills.py`.
- `README.md`, `docs/ENGINES.md`, `agent-wiki/2026-10-30-vllm-source-build.md`, `CHANGES.md`.

## Not covered

- `sglang/cuda` (#938) — the analogous conversion, on a separate branch/PR.
- `tensorrt-llm` (#939, held for an owner decision on measuring NVIDIA's own build).
- `ollama` (×4, #936) — blocked on owner admission.
- The sweep mechanism (#614) and per-SM images.
