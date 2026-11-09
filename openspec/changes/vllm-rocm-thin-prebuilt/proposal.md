# vllm-rocm-thin-prebuilt — build the rocm cell on AMD's official rocm/vllm base (prebuilt: true), and route its pushless local verify builds to the docker driver

## Why

The vllm rocm cell previously source-compiled the pinned sha on the shared devel base (with an
`-e .` overlay that tried to build the `rocm==0.1.0` placeholder under `--no-build-isolation`,
dying `ModuleNotFoundError: No module named 'poetry'` — issue #1558) and, when it did build, was a
40~75-min cold cell that could ENOSPC the container driver's export+load (~3x) on its ~60+ GiB
unpacked base (issue #1915 class, run 42531128064).

## What changes

The rocm cell is **thin-prebuilt**: `FROM docker.io/rocm/vllm:rocm10.1.0_ubuntu24.04_py3.14-pytorch_2.13.0_vllm-0.29.0`
+ the llgenie entrypoint/healthcheck wrap, `prebuilt: true`, `install: []` (zero steps, no `-e .`,
no poetry, no compile). The same engine code shipped to main via #2429; this PR adds the rocm
`NO_CACHE_EXPORT` entry in `scripts/engine_image.py` so a pushless local verify (`--load`) builds on
the `docker` driver instead of the container-driver's export+load that ENOSPC'd.

## Out of scope

- The cuda / cpu cells (cuda is its own thin change #2386/#2429; cpu stays source-compiled).
- Whether the rocm image serves on a real ROCm host (this host has no ROCm device; the CI/verify
  evidence is the binary `detect` tier, issue #2319).
- AC-3 (`push=true` publish) — the post-merge producer sweep owned by #2290.
