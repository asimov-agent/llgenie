# SGLang/cuda build-engine fails — param bypasses uv for the pip steps (#1242)

## Why

`make build-engine ENGINE=sglang ARCH=cuda` fails at Dockerfile.cuda [5/5]
(`python3 engine_runner.py install params.json`), because the committed param
calls `python3 -m pip` in `llgenie/base-cuda:79cfaf25ba`, whose system Python
has no `pip` module. Failure (run 41245076650 @ `abc1d3ac`):
`/usr/bin/python3: No module named pip` → `[engine-runner] FAIL sglang/cuda:
step exited 1` → `[engine-image] FAIL build llgenie/sglang:...-cuda`.

The base-cuda image provides `uv` (COPY from astral-sh/uv into
`/opt/llgenie/bin`, on `PATH`), so every other CUDA engine uses
`uv pip install --system --break-system-packages` (vllm, tensorrt-llm,
litert, freetoken, mlx cuda, sglang's own torch step). sglang's two
`python3 -m pip` steps (the `python[all]` editable install and the AOT
kernels editable install) are the only ones that bypass uv, which is why
this cell alone fails on the shared base.

## What changes

1. `skills/engines/sglang/SKILL.md`: change the two `install.cuda` steps that
   call `python3 -m pip install` to `uv pip install --system
   --break-system-packages` (dropping `--no-cache-dir`, as uv's default is
   off-build caching and the Dockerfile already removes `/root/.cache`), so
   they run with the same uv bootstrap every other CUDA engine uses. Because
   the uv read surfaced it (the old pip path never ran — pip was missing),
   also correct the editable spec from `-e 'python[all]'` to `-e '.[all]'`:
   the step already `cd`s into `{src}/python`, so `python` was resolved as a
   non-existent relative path (`{src}/python/python`), failing the install
   (`error: Distribution not found`).
2. `make generate-engine-params ENGINE=sglang`; commit the regenerated
   `containers/engines/params/sglang.json` + `containers/engines/dockerfiles/sglang/Dockerfile.cuda`.
3. sglang's `all`-extras cuda-tile dependency builds with the `wheel_stub`
   backend and sglang-kernel's aot package with `scikit-build-core`, both of
   which `--no-build-isolation` does not fetch — preinstall both
   (`wheel_stub scikit-build-core`) in the cuda install steps (uv's own
   diagnostics from the runs: wheel_stub on run 41253216593, scikit-build-core
   on run 41253604264). Also preinstall a `cmake` (4.x) wheel: sglang-kernel's
   aot/CMakeLists calls `cmake_policy(SET CMP0169/CMP0177 ...)` unguarded, and
   those are CMake 4.x-only policies the distro 3.28 hard-errors on
   (`Policy "CMP0169" is not known to this version of CMake`, run 41254674809).
   Finally cap `SGL_KERNEL_COMPILE_THREADS=4` in the aot build's CMAKE_ARGS:
   upstream defaults to `--threads=32`, which OOM'd the CI hosted runner
   mid-compile ("The hosted runner lost communication ... starves it for
   CPU/Memory", run 41255470647).
4. Verify with `make build-engine ENGINE=sglang ARCH=cuda` (this lane never
   builds an engine image locally — CI is the builder — so the cell is proven
   on the CI `engine-image-sglang-cuda` run from this PR head), then
   `make test-engine-stage TEST=detect`.

## Impact

- `skills/engines/sglang/SKILL.md`, `containers/engines/params/sglang.json`,
  `containers/engines/dockerfiles/sglang/Dockerfile.cuda`.
- Affected gates: `make check-engine-params`, `make check-engine-source`,
  `make check-engine-coverage`.
- `agent-wiki/2026-10-31-sglang-cuda-pip-bootstrap.md`, `CHANGES.md`.

## Not covered

- #1240 (cuda-CDI install-leg gap) — separate issue, separate branch.
- #1241 (vllm torch-index pin) — separate issue, separate branch.
- #1196 (mkdir fix) — uninvolved.
- The rocm cell keeps `pip list`/`python3 -m pip` — its base
  (`rocm/pytorch:...`) is a full PyTorch image with pip present; the cuda
  base is the pip-less one, and the issue scope is cuda only.
