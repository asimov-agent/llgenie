# trtllm-cuda-source-build-fit

## ADDED Requirements

### Requirement: The tensorrt-llm cuda source-build fit is measured and recorded

The tensorrt-llm/cuda source-build outcome MUST be measured in a time-boxed attempt at the pinned
sha `376f7e1b` in the CUDA devel base, running `scripts/build_wheel.py --trt_root /opt/tensorrt
--cuda_architectures 89-real -j 16`, and the wall-clock, peak disk and outcome MUST be recorded. If
the measured fit does not satisfy the CI budget, the cell stays `prebuilt: true` and the skill MUST
carry a dated decision naming the measured numbers and the command attempted, with the README
engine-image rule naming tensorrt-llm as a recorded exception.

#### Scenario: the measurement completes and the cell converts

Given the tensorrt-llm cuda cell is `prebuilt: true` with the PyPI-wheel install,
When a time-boxed source build at pin `376f7e1b` fits the CI budget,
Then the cell converts to `prebuilt: false` with a pinned clone and the upstream build in
`install.cuda`, the params/Dockerfiles are regenerated, and `make build-engine` with
`make test-engine-stage … TEST=detect` are green.

#### Scenario: the measurement does not fit and the cell stays prebuilt

Given the measured wall-clock or peak disk exceeds the CI budget,
When `prebuilt: true` is kept and the reason is written into
`skills/engines/tensorrt-llm/SKILL.md` as a dated decision naming the measured numbers and the
command attempted,
Then the README engine-image rule names tensorrt-llm as a recorded exception while it stays
prebuilt.
