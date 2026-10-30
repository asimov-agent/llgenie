# sglang-cuda-source-build

## MODIFIED Requirements

### Requirement: sglang/cuda builds from the pinned source, not the PyPI wheel

The `sglang` skill's `install.cuda` MUST clone `sgl-project/sglang` at `pinned:` and build it in
place (the main pyproject's `--no-build-isolation` editable install of `python[all]`, then the
AOT CUDA kernels via `aot/CMakeLists`' scikit-build-core build), and the `container.cuda` block
MUST no longer carry `prebuilt: true` (the image is built FROM the shared cuda devel base and the
cloned source runs `engine_runner.py install`). The CUDA arch list MUST be passed to the compiler
as `CMAKE_CUDA_ARCHITECTURES` from the shared fat list.

#### Scenario: sglang/cuda compiles the pinned sha with the fat arch list

Given the `sglang` skill and shared generator,
When  `make generate-engine-params ENGINE=sglang` renders the cuda variant,
Then  `prebuilt` is false, `base` is the shared cuda devel base, `CUDA_ARCH` is
`75;80;86;89;90;120`, and `install.cuda` clones the pinned sha, installs `python[all]`, and
compiles the AOT kernels with `CMAKE_ARGS='-DCMAKE_CUDA_ARCHITECTURES=75;80;86;89;90;120'`.

- **Test:** `tests/test_engine_source_guard.py::test_the_census_matches_the_committed_params` and
  `tests/test_engine_skills.py::test_official_upstream_images_are_used_as_bases`

#### Scenario: no sglang/cuda wheel or upstream-base install remains

Given the committed `containers/engines/params/sglang.json`,
When  the source-build guard runs,
Then  `make check-engine-source` has no finding for `sglang/cuda` (it downloads no
`sglang=={version}` wheel and its Dockerfile does not start `FROM lmsysorg/sglang`).

- **Test:** `tests/test_engine_source_guard.py::test_the_census_matches_the_committed_params` and
  `tests/test_engine_skills.py::test_official_upstream_images_are_used_as_bases`

### Requirement: The cuda cell builds and its binary answers its documented flags

When the engine-build workflow builds a sglang cuda image, the build MUST succeed and the image's
binary MUST answer the flags the skill documents.

#### Scenario: a built sglang/cuda cell answers its documented flags

Given the committed params and a sglang image built by the engine-build workflow,
When  `make build-engine ENGINE=sglang ARCH=cuda` then `make test-engine-stage ENGINE=sglang ARCH=cuda TEST=detect` run,
Then  the build succeeds and the image's binary answers the flags the skill documents.

- **CI job** `engine-image-sglang-cuda` -> `make build-engine` + `make test-engine-stage TEST=detect`

### Requirement: The affected source-guard census and base tests move with the change

When a cell changes from `prebuilt: true` to a source build, the committed params that pin the
census and the official-image test MUST be updated in the same commit.

#### Scenario: sglang/cuda's conversion shifts the census to 23 source / 8 prebuilt

Given the change converts sglang/cuda (vllm's three cells stay prebuilt on this branch),
When  `tests/test_engine_source_guard.py::test_the_census_matches_the_committed_params` runs,
Then  it reads 23 `prebuilt: false` and 8 `prebuilt: true` cells (31 total).

- **Test:** `tests/test_engine_source_guard.py::test_the_census_matches_the_committed_params`
