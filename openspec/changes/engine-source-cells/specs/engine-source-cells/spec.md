# engine-source-cells

## ADDED Requirements

### Requirement: A cell that converts to a source build loses its tracked exception

When a cell's `install.<backend>` compiles the engine from its pinned checkout, its entry in
`scripts/engine_source_guard.py::KNOWN_NOT_SOURCE` MUST be deleted in the same commit, so
`make check-engine-source` fails — naming that engine/arch — if the recipe ever regresses to a wheel,
a release archive, or an upstream image.

#### Scenario: a converted cell has no tracked exception left
Given `freetoken/cuda`, `mlx/cpu`, `mlx/cuda`, `tensorfold/cuda` and `litert/cpu` were the five
tracked entries,
When  the first four are converted and `litert/cpu` keeps its recorded decision,
Then  `make check-engine-source` reports 21 of the 22 `prebuilt: false` cells running their own build
and exactly one tracked exception (`litert/cpu`), and exits 0.

- **Test:** `tests/test_engine_source_guard.py::test_the_census_matches_the_committed_params` and
  `tests/test_engine_source_guard.py::test_a_tracked_exception_passes_the_gate_but_is_reported`

#### Scenario: a regression names the cell
Given a converted cell whose install step is replaced by a wheel install,
When  `make check-engine-source` runs,
Then  it exits non-zero and its message names that engine/arch.

- **Test:** `tests/test_engine_source_guard.py::test_a_wheel_cell_that_claims_a_build_is_a_finding`

#### Scenario: a Zig build is a source build
Given a cell whose install clones the pin and runs the project's own `zig build` with its `-Dsm` arch
list,
When  the guard looks at it,
Then  it has no finding, because `zig build` is a recognised build command.

- **Test:** `tests/test_engine_source_guard.py::test_a_zig_cell_that_builds_from_source_passes`

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
  and `tests/test_engine_source_guard.py::test_every_cell_converted_by_615_is_a_source_build_in_the_committed_params`

#### Scenario: every converted cell's committed params build from a pinned clone
Given the four cells this change converted (`freetoken/cuda`, `mlx/cpu`, `mlx/cuda`, `tensorfold/cuda`),
When  their committed params are read,
Then  none says `prebuilt: true`, every one names a `git clone` at a pinned sha, and the guard has no
finding for them.

- **Test:** `tests/test_engine_source_guard.py::test_every_cell_converted_by_615_is_a_source_build_in_the_committed_params`

#### Scenario: each cell is built and its binary answers its documented flags
Given the regenerated params and a built image,
When  `make build-engine ENGINE=<id> ARCH=<arch>` then
`make test-engine-stage ENGINE=<id> ARCH=<arch> TEST=serve|detect` run,
Then  the build succeeds and the image's binary answers the flags the skill documents, a cpu cell also
answering `/v1/chat/completions`.

- **CI jobs** `engine-image-<id>-<arch>` -> `make build-engine` + `make test-engine-stage TEST=serve` (cpu)
  / `TEST=detect` (gpu), dispatched by `gh workflow run engine-build.yml -f engine=<id> -f arch=<arch>`

### Requirement: A cell that cannot be built here records a dated decision

Where a cell genuinely cannot be built in this repository, its engine skill MUST carry a dated decision
block naming the measured blocker — the command that was attempted, the wall-clock and the disk it
reached — and the cell MUST keep its `KNOWN_NOT_SOURCE` entry, so the gate reports the exception with
its issue instead of passing a `prebuilt: false` claim it does not honour.

`prebuilt: true` is NOT the form for such a cell when the engine has no upstream image: in this
generator it means "the image starts `FROM` the engine's official image", so for a pip-installed engine
it would emit an image that contains no engine at all.

#### Scenario: litert/cpu's Bazel wheel has no in-repo build of the served CLI
Given the LiteRT-LM tree at the pin builds `litert-lm` only as a Bazel `py_wheel` over a Git-LFS
`prebuilt/<os>/libLiteRt.so`, its `bazel build //python/litert_lm_cli:wheel` dies at repository mapping
in 92 s, and its C++ `//runtime/engine:litert_lm_main` is a different CLI than `litert-lm serve`,
When  the source build is attempted and measured,
Then  the skill carries the dated decision with those numbers, the params keep the wheel install, and
`make check-engine-source` reports `litert/cpu` as the one tracked exception.

- **Test:** `tests/test_engine_source_guard.py::test_a_tracked_exception_passes_the_gate_but_is_reported`
  and `tests/test_engine_source_guard.py::test_the_census_matches_the_committed_params`

### Requirement: Out-of-scope conversions are their own linked issues

The nine cells that honestly say `prebuilt: true` (`ollama` ×4, `vllm` ×3, `sglang/cuda`,
`tensorrt-llm/cuda`) MUST each be filed as its own issue carrying the measured-cost precondition, linked
from this change's `Not covered` section, rather than folded into this change.

#### Scenario: the nine prebuilt cells are tracked work, not prose
Given this change converts the five mislabelled cells,
When  the change is reviewed,
Then  four linked issues (#936 ollama, #937 vllm, #938 sglang/cuda, #939 tensorrt-llm) each carry their
own acceptance criteria, and the PR body names them in `Not covered`.

- **Test:** the PR body of this change, `Not covered` section, linking #936, #937, #938 and #939; each of
  those issues names #615 as the issue it was split from.
