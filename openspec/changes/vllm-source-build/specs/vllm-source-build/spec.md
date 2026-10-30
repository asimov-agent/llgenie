# vllm-source-build

## MODIFIED Requirements

### Requirement: vLLM's three cells build from the pinned source, not a wheel

The `vllm` skill's `install.cuda`, `install.rocm` and `install.cpu` MUST clone
`vllm-project/vllm` at `pinned:` and build it in place with vLLM's own `--no-build-isolation`
editable install, and the `container` blocks for those backends MUST no longer carry
`prebuilt: true` (so the image is built FROM the shared devel base for that backend and the
released source runs `engine_runner.py install`). The backend's arch list MUST be passed to the
compiler: `CMAKE_CUDA_ARCHITECTURES` from the shared fat CUDA list for cuda, `PYTORCH_ROCM_ARCH`
from the shared fat gfx list for rocm.

#### Scenario: vllm/cuda compiles the pinned sha with the fat arch list

Given the `vllm` skill and shared generator,
When  `make generate-engine-params ENGINE=vllm` renders the cuda variant,
Then  `prebuilt` is false, `base` is the shared cuda devel base, `CUDA_ARCH` is
`75;80;86;89;90;120`, and `install.cuda` clones the pinned sha and runs
`VLLM_TARGET_DEVICE=cuda uv pip install --no-build-isolation -e .` with
`CMAKE_ARGS='-DCMAKE_CUDA_ARCHITECTURES=75;80;86;89;90;120'`.

- **Test:** `tests/test_engine_source_guard.py::test_the_census_matches_the_committed_params` and
  `tests/test_engine_skills.py::test_official_upstream_images_are_used_as_bases`

#### Scenario: vllm/rocm and vllm/cpu similarly build from the pinned sha

Given the regenerated rocm and cpu variants,
When  their params are read,
Then  neither says `prebuilt: true`; rocm passes `PYTORCH_ROCM_ARCH` from the shared fat gfx
list with `VLLM_TARGET_DEVICE=rocm`, and cpu passes `VLLM_TARGET_DEVICE=cpu`, both via `--no-build-isolation
pip install -e .` of the cloned pin.

- **Test:** `tests/test_engine_source_guard.py::test_the_census_matches_the_committed_params`

#### Scenario: no vllm cell reports a wheel, archive or upstream-base install

Given the committed `containers/engines/params/vllm.json`,
When  the source-build guard runs,
Then  `make check-engine-source` has no finding for any `vllm` cell (none downloads a `vllm==`
wheel, none starts `FROM vllm/vllm-openai*`).

- **Test:** `tests/test_engine_source_guard.py::test_the_census_matches_the_committed_params` and
  `tests/test_engine_skills.py::test_official_upstream_images_are_used_as_bases`

### Requirement: Each vllm cell builds and its binary answers its documented flags

When the engine-build workflow builds a vllm image, the build MUST succeed and the image's
binary MUST answer the flags the skill documents; the cpu cell MUST also answer
`/v1/chat/completions`.

#### Scenario: a built vllm cell answers its documented flags

Given the committed params and a vllm image built by the engine-build workflow,
When  `make build-engine ENGINE=vllm ARCH=<arch>` then `make test-engine-stage ENGINE=vllm ARCH=<arch> TEST=detect` run,
Then  the build succeeds and the image's binary answers the flags the skill documents (the cpu
cell also answering `/v1/chat/completions`).

- **CI jobs** `engine-image-vllm-<arch>` -> `make build-engine` + `make test-engine-stage TEST=serve` (cpu) / `TEST=detect` (gpu)

### Requirement: The affected source-guard census and base tests move with the change

When a cell changes from `prebuilt: true` to a source build, the committed params that pin the
census and the official-image test MUST be updated in the same commit.

#### Scenario: vllm's conversion shifts the census to 25 source / 6 prebuilt

Given the change converts vllm's three cells (sglang/cuda stays prebuilt on this branch),
When  `tests/test_engine_source_guard.py::test_the_census_matches_the_committed_params` runs,
Then  it reads 25 `prebuilt: false` and 6 `prebuilt: true` cells (31 total).

- **Test:** `tests/test_engine_source_guard.py::test_the_census_matches_the_committed_params`
