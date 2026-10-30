# SGLang/cuda builds from the pinned source, not the PyPI wheel (#938)

**Issue:** #938 · **PR:** this change's PR · **Branch:** `agent/issue-938-sglang-source-build`
**Split out of #615** — the "Prebuilt cells build from source" follow-up for `sglang`'s cuda cell.

## What changed

`sglang` had one cell (`cuda`) that said `prebuilt: true` and installed the engine from PyPI
(`uv pip install sglang=={version}`), while the rocm cell already cloned the tree and built from
source. This change ports the rocm shape to cuda:

1. `install.cuda` clones `sgl-project/sglang` @ `35ce3132…` (= v0.5.22), preinstalls
   `torch==2.14.1` from the cu130 index (the main pyproject needs it for
   `--no-build-isolation`), `SETUPTOOLS_SCM_PRETEND_VERSION=0.5.22 python3 -m pip install
   --no-build-isolation -e 'python[all]'`, then compiles the AOT CUDA kernels
   (`aot/CMakeLists` via scikit-build-core) with
   `CMAKE_ARGS='-DCMAKE_CUDA_ARCHITECTURES=75;80;86;89;90;120'` (the shared fat list).
2. `container.cuda` dropped `prebuilt: true`; the image is built FROM the shared cuda devel base
   (`nvidia/cuda:13.0.2-devel`), adding `rustc-1.91`/`cargo-1.91` (sglang's setuptools-rust
   build needs edition-2024 cargo), `python3-dev` and `wget`.
3. `hw_flags.cuda.cuda_arch` keys the cuda variant to the shared `FAT_CUDA_ARCHS`.

## What was verified

- `make generate-engine-params ENGINE=sglang` rewrites `params/sglang.json` and
  `Dockerfile.cuda`: `FROM llgenie/base-cuda:<hash>` and `python3 engine_runner.py install`.
- `make check-engine-source`: the census is 23 source / 8 prebuilt on this branch (vllm's three
  cells stay prebuilt here; that is #937); `sglang/cuda` has no finding.
- The affected tests (`test_engine_source_guard.py`, `test_engine_skills.py`) pass; the
  engine gates (`check-engine-source`/`-params`/`-coverage`) are green.
- The image build (`make build-engine ENGINE=sglang ARCH=cuda`) and
  `make test-engine-stage … TEST=detect` run on the CI `engine-image-sglang-cuda` job; this host
  pulls and verifies, never builds.

## Not covered

`tensorrt-llm/cuda` (#939, held for an owner decision), `vllm` (×3, #937, a separate PR),
`ollama` (#936, blocked on owner admission), the sweep (#614).
