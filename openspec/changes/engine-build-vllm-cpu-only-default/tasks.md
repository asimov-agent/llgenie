# Tasks

- [x] `scripts/engine_image.py` `matrix()`: when `arch=""` the vllm engine emits only its `cpu` variant — no vllm `cuda`/`rocm` cell in the default whole-set sweep.
- [x] `ARCH=cuda` / `ARCH=rocm` still emits the vllm GPU cell (the explicit `arch` filter is unchanged).
- [x] A test asserts the default vllm matrix contains `cpu` and excludes `cuda`/`rocm`, and that explicit `arch=cuda`/`arch=rocm` builds the GPU variant.
- [x] `make ci-lint` + `make ci-unit` green (the engine-matrix unit suite, incl. the new test, passes).
- [x] Docs trio per #1123: `agent-wiki/` note + `docs/changes.d/` fragment + `CHANGES.md` regenerated.
- [x] PR opens `closes #1836`; normal review flow (#1644 acceptance write-back, owner merges).
