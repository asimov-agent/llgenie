# tensorrt-llm/cuda — measured: source build does NOT fit the CI budget (#939)

Recorded 2026-11-02. Implements issue #939 (measure the source-build fit and record the outcome) via PR #1542.

## Measurement (the acceptance criterion)

A time-boxed source build of NVIDIA/TensorRT-LLM at the pinned sha `376f7e1b` was launched in the
NGC CUDA devel base (`nvcr.io/nvidia/tensorrt-llm/devel:1.2.1`) running upstream's own entry point:

```
scripts/build_wheel.py --trt_root /opt/tensorrt --cuda_architectures 89-real -j 16
```

Measured against the CI budget the `engine-build` job actually runs under: **GitHub-hosted
`ubuntu-latest` (4 vCPU), `timeout-minutes: 240`, ~14 GB free disk after the Free-disk step**.

### Numbers measured on this 32-core host (an optimistic upper bound — CI is 4 vCPU)

- Git-LFS clone at the pin, excluding venv/build: **5.2 GB** (8.6 GB once the `.venv-3.12` +
  `cpp/build` tree exists).
- Object compile: **1477 of 5460 source targets in 21 min** at `-j16` (1592% CPU, 14.3 GB RAM),
  with the remaining targets the heavy cutlass/`moe_gemm` instantiations that take minutes each →
  extrapolated **~90–120 min of object compile on this host before wheel/link**.
- On the 4-vCPU `ubuntu-latest` the engine-build job uses, that is **~4–8× slower → 6–6+ hours**,
  far past the **240-min** timeout.
- Working tree already **9.5 GB** and climbing after 21 min — clone+venv+build **approaches the
  runner's ~14 GB free-disk budget before the multi-GB devel base image and wheel assembly**.

## Decision

**Does not fit the CI budget. Keep `prebuilt: true`** (PyPI wheel on the NGC release base). The
dated decision with these numbers is recorded in `skills/engines/tensorrt-llm/SKILL.md`, and the
README engine-image rule + `docs/ENGINES.md` now name tensorrt-llm as a recorded exception alongside
litert/cpu. Revisit when upstream ships a wheel-free build that fits a CI budget (delete the skill
decision comment and the `KNOWN_NOT_SOURCE`-style record then).
