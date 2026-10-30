# SGLang/cuda builds from the pinned source, not the PyPI wheel (#938)

## Why

`sglang` has two cells with different provenance. The rocm cell clones the tree at the tag and
builds its AOT kernels (`setup_rocm.py`, `pyproject_other.toml`) — a real source build. The cuda
cell says `prebuilt: true` and its skill installs the PyPI wheel (`uv pip install
sglang=={version}`). One engine, two recipes, and the cuda cell is the one that cannot be
rebuilt here — a CUDA/torch skew in the base is invisible to half the matrix.

## What changes

1. `skills/engines/sglang/SKILL.md`: give `install.cuda` the rocm cell's shape — clone
   `sgl-project/sglang` at `pinned:`, preinstall torch 2.14.1 from the cu130 index (the main
   pyproject needs it for `--no-build-isolation`), `pip install --no-build-isolation -e
   'python[all]'`, then compile the AOT CUDA kernels in place via `aot/CMakeLists`
   (scikit-build-core) with `CMAKE_CUDA_ARCHITECTURES` from the shared fat list.
2. Drop `prebuilt: true` from the cuda cell; build on the shared cuda devel base with
   `rustc-1.91`/`cargo-1.91` (sglang's setuptools-rust build needs edition-2024 cargo),
   `python3-dev` and `wget`.
3. `make generate-engine-params ENGINE=sglang`, commit params + both Dockerfiles.
4. `make build-engine ENGINE=sglang ARCH=cuda` then `make test-engine-stage … TEST=detect`.

## Impact

- `skills/engines/sglang/SKILL.md`, `containers/engines/params/sglang.json`,
  `containers/engines/dockerfiles/sglang/Dockerfile.cuda`.
- `tests/test_engine_source_guard.py` (census: 23 source / 8 prebuilt on this branch — vllm stays
  prebuilt, that is #937), `tests/test_engine_skills.py`.
- `README.md`, `docs/ENGINES.md`, `agent-wiki/2026-10-30-sglang-cuda-source-build.md`,
  `CHANGES.md`.

## Not covered

- `tensorrt-llm` (#939, held for an owner decision).
- `vllm` (×3, #937) — the analogous conversion, on a separate branch/PR.
- `ollama` (×4, #936) — blocked on owner admission.
- The sweep mechanism (#614) and per-SM images.
