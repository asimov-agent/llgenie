# vLLM cuda cell installs the pinned prebuilt CUDA wheel instead of source-compiling (#2386)

**Issue:** #2386 · **PR:** this change's PR · **Branch:** `llgenie-engines-vllm-cuda-wheel` · **head** TBD

## What changed

The vLLM `cuda` cell (`make build-engine ENGINE=vllm ARCH=cuda`) stopped source-compiling the
pinned sha and now installs vLLM's official prebuilt CUDA wheel. Supersedes #937/#615's anti-wheel
direction **for the cuda cell only** (the ABI-skew case rebutted in the issue: base CUDA 13.0.2
matches the wheel's cu13 build, torch resolves from the same cu130 index the source build used,
and vLLM's fat CUDA wheels keep a fixed arch set).

The `install.cuda` steps in `skills/engines/vllm/SKILL.md` are now:

1. `curl -fSL --retry 3 -o …/vllm.whl https://files.pythonhosted.org/packages/8b/a8/…-vllm-0.33.0-cp38-abi3-manylinux_2_28_x86_64.whl`
2. `echo '<sha256> …/vllm.whl' | sha256sum -c -` — fails the build on any hash mismatch
3. `uv pip install --system --break-system-packages torch==2.14.0 torchvision==0.29.0 torchaudio==2.11.0 torchcodec --index-url https://download.pytorch.org/whl/cu130`
4. `uv pip install --system --break-system-packages …/vllm.whl && rm -f …/vllm.whl`

The four source-compile steps (`git clone`, `-r requirements/build/cuda.txt`,
`tools/build_rust.sh`, `-e .`) are gone **for the cuda cell only**. The base stays
`FROM llgenie/base-cuda:79cfaf25ba`. `install.rocm` / `install.cpu` are unchanged (still
source-compiled at the pin).

`scripts/engine_source_guard.py`: `("vllm", "cuda")` added to `KNOWN_NOT_SOURCE` — the wheel
install is a pull, not a source build, so `check-engine-source` stays green.

## What was verified

- `make generate-engine-params ENGINE=vllm` → `containers/engines/params/vllm.json` cuda
  install is the 4-step wheel flow; rocm/cpu still `git clone` + `-e .`.
- `make check-engine-source` → `OK: 27 of 30 … 3 tracked in issue #615` (vllm/cuda now tracked).
- `make check-engine-params` → `0 file(s) stale`.
- `tests/test_engine_skills.py::test_vllm_cuda_installs_the_wheel_not_a_source_step` +
  `tests/test_engine_source_guard.py` + `tests/test_ci_variant_matrix.py`: 125 passed in the
  `llgenie/test` container (regression to a source step reds).
- CI `engine-image-vllm-cuda` cell: **TBD** (run id in the finish comment).

## Anything left open

- The published cuda tag must come from the producer run at the PR head; this lane never builds
  an engine image locally.
