# engine-source-cells

## ADDED Requirements

### Requirement: A cell that converts to a source build loses its tracked exception

When a cell's `install.<backend>` compiles the engine from its pinned checkout, its entry in
`scripts/engine_source_guard.py::KNOWN_NOT_SOURCE` MUST be deleted in the same commit, so
`make check-engine-source` fails — naming that engine/arch — if the recipe ever regresses to a wheel,
a release archive, or an upstream image.

#### Scenario: a converted cell has no tracked exception left
Given `freetoken/cuda`, `mlx/cpu`, `mlx/cuda`, `tensorfold/cuda` and `litert/cpu` were the only
tracked entries,
When  every one of them is converted or carries the dated decision,
Then  `make engine-source-report` lists 0 tracked exceptions and `make check-engine-source` exits 0.

- **Test:** `tests/test_engine_source_guard.py::test_the_census_matches_the_committed_params` and
  `tests/test_engine_source_guard.py::test_a_tracked_exception_passes_the_gate_but_is_reported`

#### Scenario: a regression names the cell
Given a converted cell whose install step is replaced by a wheel install,
When  `make check-engine-source` runs,
Then  it exits non-zero and its message names that engine/arch.

- **Test:** `tests/test_engine_source_guard.py::test_a_wheel_cell_that_claims_a_build_is_a_finding`

### Requirement: A converted cell's committed params are a source build after generation

`make generate-engine-params ENGINE=<id>` MUST write install steps that contain the pinned checkout and the
engine's own build command, for every backend the cell declares; the committed
`containers/engines/params/<id>.json` and `containers/engines/dockerfiles/<id>/Dockerfile.<arch>` are that
output and are committed with the change.

#### Scenario: mlx's two image cells carry the core build
Given the mlx skill's `install.cpu` and `install.cuda` name `ml-explore/mlx` at `1f8e74e3…` and an
`uv pip install` of that tree,
When  `make generate-engine-params ENGINE=mlx` runs,
Then  `params/mlx.json` prebuilt is false for both cells, its install steps contain the clone and the
`CMAKE_ARGS` build, and `make check-engine-source` passes for them.

- **Test:** `tests/test_engine_source_guard.py::test_the_manifest_of_a_converted_engine_is_a_source_build_after_generate`

#### Scenario: each cell is built and its binary answers its documented flags
Given the regenerated params and a built image,
When  `make build-engine ENGINE=<id> ARCH=<arch>` then
`make test-engine-stage ENGINE=<id> ARCH=<arch> TEST=serve|detect` run,
Then  the build succeeds and the image's binary answers the flags the skill documents, a cpu cell also
answering `/v1/chat/completions`.

- **CI jobs** `engine-image-<id>-<arch>` -> `make build-engine` + `make test-engine-stage TEST=serve` (cpu)
  / `TEST=detect` (gpu), dispatched by `gh workflow run engine-build.yml -f engine=<id> -f arch=<arch>`

### Requirement: A cell that cannot be built here records a dated decision

Where a cell genuinely cannot be built in this repository, its params MUST say `prebuilt: true` and its
skill MUST carry a dated decision block naming the measured blocker — the command that was attempted, the
wall-clock and the disk it reached — instead of a `prebuilt: false` claim it does not honour.

#### Scenario: litert/cpu's Bazel wheel has no in-repo build of the served CLI
Given the LiteRT-LM tree at the pin has no `pyproject.toml` and its CMake super-build produces
`litert_lm_main` rather than the `litert-lm serve` CLI the skill wraps,
When  the source build is attempted and measured,
Then  the skill carries the dated decision with those numbers, and the params say `prebuilt: true`.

- **Test:** `tests/test_engine_source_guard.py::test_a_prebuilt_cell_is_never_a_finding`
