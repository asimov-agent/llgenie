# tensorrt-llm/cuda — measure the source-build fit and record the outcome (#939)

## Why

`tensorrt-llm/cuda` says `prebuilt: true` and its skill installs the PyPI wheel
(`uv pip install tensorrt_llm=={version}`) on NVIDIA's NGC torch base. NVIDIA builds
TensorRT-LLM itself with a multi-hour CMake pipeline against TensorRT, and this repository has
never compiled it. Without a measured answer the cell stays a wheel that looks like a build in the
sweep, and a TensorRT version bump in the base can change the runtime under a pin nobody rebuilt.

## What changes

1. A time-boxed source-build attempt at the pinned sha `376f7e1b` in the CUDA devel base
   (`nvcr.io/nvidia/tensorrt-llm/devel:1.2.1`), running upstream's own documented build
   (`scripts/build_wheel.py --trt_root /opt/tensorrt --cuda_architectures 89-real -j 16`),
   recording wall-clock, peak `/src` disk and the failure mode (or the built-wheel path).
2. Either the cell converts to a real build (`prebuilt: false`, pinned clone + upstream build,
   generated params committed, `make build-engine` + `make test-engine-stage … TEST=detect` green),
   or it stays prebuilt **and** the skill carries a dated decision naming the measured numbers and
   the command that was attempted.

## Spec

See `specs/trtllm-cuda-source-build-fit/spec.md`.

## Tasks

- [ ] Time-boxed source-build attempt at pin `376f7e1b` in the CUDA devel base; wall-clock, peak disk, outcome recorded
- [ ] Convert the cell to a source build (`prebuilt: false`) or keep `prebuilt: true` with a dated decision in the skill
- [ ] Regenerate params/Dockerfiles; `make build-engine` + `make test-engine-stage … TEST=detect` green (if converted)
- [ ] Wiki note records the measurement (references the issue and the PR)
- [ ] README engine-image rule names tensorrt-llm as a recorded exception while it stays prebuilt
- [ ] Open one ready-for-review PR closing #939; gates through make; never merge
