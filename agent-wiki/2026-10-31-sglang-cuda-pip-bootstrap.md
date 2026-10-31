# SGLang/cuda build-engine fails — the pip steps run through the cuda base's uv (#1242)

**Issue:** #1242 · **PR:** this change's PR · **Branch:** `fix/1242-sglang-pip-bootstrap`

## Problem

`make build-engine ENGINE=sglang ARCH=cuda` failed at `Dockerfile.cuda` [5/5]
(`python3 engine_runner.py install params.json`), because the committed param
`containers/engines/params/sglang.json:33` called `python3 -m pip`, but the shared
cuda build base (`llgenie/base-cuda:79cfaf25ba`) has **no pip module** in its system
Python — `/usr/bin/python3: No module named pip` (engine-build run 41245076650 @
`abc1d3ac`). The base provides `uv` instead (COPY from `astral-sh/uv` into
`/opt/llgenie/bin`, on `PATH`), and every other CUDA engine already installs with
`uv pip install --system --break-system-packages` — only sglang's cuda cell bypassed
uv for two pip steps.

## What changed

1. `skills/engines/sglang/SKILL.md`: the two `install.cuda` steps that called
   `python3 -m pip install` now use `uv pip install --system --break-system-packages`
   (dropping `--no-cache-dir`, matching the sibling CUDA engines vllm / tensorrt-llm /
   litert / freetoken, and sglang's own torch preinstall step). Because the uv read
   surfaced it (the pip path never ran — pip was missing), the editable spec was also
   corrected from `-e 'python[all]'` to `-e '.[all]'`: the step already `cd`s into
   `{src}/python`, so `python` resolved to the non-existent `{src}/python/python`
   path (`error: Distribution not found`, engine-build run 41251817822).
2. `make generate-engine-params ENGINE=sglang` regenerated `containers/engines/params/
   sglang.json` (only `variants.cuda.install` changed; rocm untouched — its base
   `rocm/pytorch:…` ships pip).
3. Added `tests/test_engine_skills.py::test_sglang_cuda_install_uses_uv_not_pip`:
   sglang/cuda's install recipe must not invoke `python3 -m pip` (the pip-less base),
   must run through the uv bootstrap, and must not carry the `-e 'python[all]'`
   relative-path form.

## What was verified

- `make generate-engine-params ENGINE=sglang` yields the uv-only cuda recipe.
- `make check-engine-params`, `make check-engine-source`, `make check-engine-coverage` green.
- `tests/test_engine_skills.py` — all 96 pass, including the new
  `test_sglang_cuda_install_uses_uv_not_pip` (ran in the `llgenie/test` container).
- The `engine-image-sglang-cuda` cell is proven on the CI engine-build run from this PR head
  (`make build-engine ENGINE=sglang ARCH=cuda` then `make test-engine-stage TEST=detect`);
  this lane pulls and verifies the published artifact, never builds an engine image locally.

## Not covered

#1240 (cuda-CDI install-leg gap), #1241 (vllm torch-index pin), #1196 (mkdir fix) — each a
separate issue/branch; rocm keeps `pip` (its base ships pip).
