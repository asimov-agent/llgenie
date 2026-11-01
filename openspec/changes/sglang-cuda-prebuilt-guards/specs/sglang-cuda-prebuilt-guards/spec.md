# sglang-cuda-prebuilt-guards

## MODIFIED Requirements

### Requirement: A prebuilt container backend validates without install steps

A skill backend whose container spec is `prebuilt: true` ships its engine in the base image, so it
MUST render ZERO install steps AND the CLI validator MUST NOT flag it for having no install steps.
The validator and the renderer share the same prebuilt special-case.

#### Scenario: a prebuilt cuda backend renders no install steps and validates clean

Given the `sglang` skill whose `container.cuda` is `prebuilt: true` and whose `install.cuda` is a
comment-only block,
When  `scripts/engine_skills.py validate` runs,
Then  it reports 0 errors (no "no install steps for backend cuda") and the rendered cuda variant
carries an empty `install` list.

- **Test:** `tests/test_engine_skills.py::test_sglang_cuda_install_is_consistent_with_its_prebuilt_flag`
  and `tests/test_engine_skills.py::test_cli_validate_against_fixture_exits_zero`

#### Scenario: a source-built cuda backend still runs its installs through uv, never pip

Given the `sglang` skill in the SOURCE state (`prebuilt` absent/false on cuda),
When  its cuda install recipe is scanned,
Then  it runs `uv pip install --system --break-system-packages`, never `python3 -m pip`, the
editable spec is `.[all]` after `cd {src}/python` (never `python[all]`), it preinstalls
wheel_stub / scikit-build-core / cmake, and capps the aot nvcc threads
(`-DSGL_KERNEL_COMPILE_THREADS`).

- **Test:** the source-branch of
  `tests/test_engine_skills.py::test_sglang_cuda_install_is_consistent_with_its_prebuilt_flag`

### Requirement: The committed cells and the guard tests agree on which backends are prebuilt

The source-guard census and the official-base Dockerfile test MUST count sglang/cuda as prebuilt
(alongside tensorrt-llm/cuda): 29 source cells, 2 prebuilt, and sglang/cuda's Dockerfile starts
FROM the official image with no install steps.

#### Scenario: the census counts sglang/cuda and tensorrt-llm/cuda as the prebuilt cells

Given every committed engine cell,
When  the source-build census is taken,
Then  there are 29 `prebuilt: false` and 2 `prebuilt: true` cells (31 total), and the only finding
is the tracked `litert/cpu` wheel cell.

- **Test:** `tests/test_engine_source_guard.py::test_the_census_matches_the_committed_params`

#### Scenario: sglang/cuda's Dockerfile starts FROM its official image and runs no install

Given the committed `containers/engines/dockerfiles/sglang/Dockerfile.cuda`,
When  the official-base test reads it,
Then  its FROM line is `lmsysorg/sglang:v0.5.22` and it does not call `engine_runner.py install`;
sglang/rocm and vllm/ollama source cells still compile.

- **Test:** `tests/test_engine_skills.py::test_official_upstream_images_are_used_as_bases`
