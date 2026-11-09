name: vllm-cuda-wheel
about: cuda cell installs the prebuilt vllm CUDA wheel instead of source-compiling the pin
status: active
---

# `engines(vllm)`: cuda cell installs the pinned prebuilt vLLM CUDA wheel (issue #2386)

## Proposal

The vLLM `cuda` cell (`make build-engine ENGINE=vllm ARCH=cuda`) today source-compiles the pinned
sha of `vllm-project/vllm` inside the shared CUDA base image: `git clone`, `uv pip install -r
requirements/build/cuda.txt`, `tools/build_rust.sh` (a Rust toolchain bootstrap) and `-e .` with
`VLLM_TARGET_DEVICE=cuda`. That path is slow, red-prone (issue #1694 hit the 240-minute timeout on
the sibling rocm cell; issue #1832 reddened the cuda cell) and depends on a Rust toolchain the base
does not ship.

This change installs vLLM's official prebuilt CUDA wheel instead, for the **cuda cell only**: keep
`FROM llgenie/base-cuda:79cfaf25ba`, `curl` the pinned wheel
(`vllm-0.33.0-cp38-abi3-manylinux_2_28_x86_64.whl`, sha256
`4b6bdec4ab269990bf70d45a3c1e94c3760a27064513760193b26d6f0da883aa`), `sha256sum -c` it, then `uv
pip install` the cu130 torch family from `--index-url https://download.pytorch.org/whl/cu130`
(`torch==2.14.0`, `torchaudio==2.11.0`, `torchvision==0.29.0`, `torchcodec>=0.14`) and the wheel.
ROCm and CPU variants stay source-compiled, unchanged.

The ABI-skew case #937/#615 were filed against is rebutted for cuda by matching the base CUDA
(13.0.2) exactly, resolving torch from the same cu130 index the source build already uses, and
installing vLLM's fat CUDA wheel (fixed arch set). No `LLGENIE_CUDA_ARCH` build arg is consumed by
the wheel path.

## Motivation

A prebuilt, hash-pinned, reproducible wheel install removes the clone, requirement-file install,
Rust bootstrap and in-place build. It cuts the cuda cell from a multi-hour, red-prone compile to a
`curl` + `pip install` that finishes in minutes. `detect` and the serve contract are unchanged.

## Change

1. `skills/engines/vllm/SKILL.md`: rewrite `install.cuda` to the wheel flow (curl + hash-check +
   cu130 torch family + wheel), record the wheel sha in the `container.cuda` block, replace the
   "no upstream wheel (issue #937)" comment. `install.rocm` / `install.cpu` unchanged.
2. `make generate-engine-params ENGINE=vllm`; commit the regenerated `params/vllm.json` and
   `containers/engines/dockerfiles/vllm/Dockerfile.cuda`.
3. `scripts/engine_source_guard.py`: add `("vllm", "cuda")` to `KNOWN_NOT_SOURCE` — the wheel
   install is a pull, not a source build — so `check-engine-source` stays green.
4. `tests/test_engine_skills.py`: a hermetic test asserting the cuda install has no source step
   (no `git clone`, `-e .`, `build_rust.sh`, `-r …/cuda.txt`) and DOES curl + hash-check the wheel.
5. `agent-wiki/2026-11-09-vllm-cuda-wheel.md` + `docs/changes.d/…` + regenerated `CHANGES.md`.

## Impact

- `skills/engines/vllm/SKILL.md`, `containers/engines/params/vllm.json`,
  `containers/engines/dockerfiles/vllm/Dockerfile.cuda`.
- `scripts/engine_source_guard.py` (census: vllm/cuda becomes a tracked known-not-source cell).
- `tests/test_engine_skills.py`, `agent-wiki/`, `docs/changes.d/`, `CHANGES.md`.

## Not covered

- ROCm and CPU vLLM variants (stay source-compiled at the pin; #1694 is their compile cost
  context). No image-size-shrink / runtime-base migration beyond what the wheel inherently changes.
- Other engines unchanged.
