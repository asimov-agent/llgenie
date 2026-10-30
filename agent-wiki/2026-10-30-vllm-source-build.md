# vLLM builds from the pinned source, not the PyPI wheel (#937)

**Issue:** #937 · **PR:** this change's PR · **Branch:** `agent/issue-937-engine-source-build`
**Split out of #615** — the "Prebuilt cells build from source" follow-up for `vllm` (×3).

## What changed

`vllm` had three container cells (`cuda`, `rocm`, `cpu`) that said `prebuilt: true` and
installed the engine from PyPI (`uv pip install vllm=={version} --torch-backend=…`) or the
`+cpu` release wheel — nothing in this repository compiled vLLM or its kernels. This change
gives each cell a source build:

| cell | install (all clone `vllm-project/vllm` @ `5df63a72…` = v0.32.0) |
|---|---|
| cuda | torch (the pin's own `requirements/build/cuda.txt` torch) from the cu-index, then `CMAKE_ARGS='-DCMAKE_CUDA_ARCHITECTURES=75;80;86;89;90;120' VLLM_TARGET_DEVICE=cuda uv pip install --no-build-isolation -e .` |
| rocm | the pin's `requirements/build/rocm.txt` (names the AMD index + torch), then `PYTORCH_ROCM_ARCH='gfx1030;…;gfx942' VLLM_TARGET_DEVICE=rocm …` |
| cpu | the pin's `requirements/build/cpu.txt`, then `VLLM_TARGET_DEVICE=cpu …` |

`container.{cuda,rocm,cpu}` dropped `prebuilt: true`; each builds on the shared devel base for
its backend, adding only `python3-dev` to the shared `BUILD_TOOLS`. `hw_flags` keys the cuda/rocm
variants to the shared `FAT_CUDA_ARCHS` / `FAT_GPU_TARGETS`, so the arch lists are the same fat
lists every other compiled engine uses.

## What was verified

- `make generate-engine-params ENGINE=vllm` rewrites `params/vllm.json` and the three
  Dockerfiles: `FROM llgenie/base-{cuda,rocm} / ubuntu` and `python3 engine_runner.py install`.
- `make check-engine-source`: 25 of 25 `prebuilt: false` vllm-row cells run their own build (the
  branch census is 25 source / 6 prebuilt — `sglang/cuda` is still prebuilt here; that is #938).
- The affected tests (`test_engine_source_guard.py`, `test_engine_skills.py`) pass.
- The per-cell image build (`make build-engine ENGINE=vllm ARCH=…`) and
  `make test-engine-stage … TEST=detect` run on the CI `engine-image-vllm-<arch>` jobs; this
  host pulls and verifies, never builds.

## Not covered

`tensorrt-llm/cuda` (#939, held for an owner decision), `sglang/cuda` (#938, a separate PR),
`ollama` (#936, blocked on owner admission), the sweep (#614).
