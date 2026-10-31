# ollama-source-build

## MODIFIED Requirements

### Requirement: Every ollama cell builds the engine from the pinned source

The `ollama` skill's `install` MUST clone `ollama/ollama` at `pinned:` and build the engine with
upstream's own Go build settings (`CGO_ENABLED=1`, `go build -trimpath -buildmode=pie`,
`-ldflags` carrying the version and `server.mode=release`), and every backend MUST additionally
compile its llama.cpp runner from the cloned tree's `llama/server` CMake presets. No ollama variant
MUST carry `prebuilt: true`, start `FROM ollama/ollama:<version>`, or download
`ollama-linux-<arch>.tar.zst`.

#### Scenario: the four ollama cells render as source builds on the shared base

Given the `ollama` skill and the shared generator,
When  `make generate-engine-params ENGINE=ollama` renders the cpu, cuda, rocm and vulkan variants,
Then  each variant has `prebuilt` false, its `base` is the shared devel base for that backend
(`llgenie/base-<backend>`), `runtime_base` is the slim runtime base, and its `install` steps clone
`ollama/ollama` at `f067033f9126993b6172bdfffa71a74ad693fda4` and run `go build`.

- **Test:** `tests/test_engine_skills.py::test_ollama_builds_from_the_pinned_go_source`

#### Scenario: no ollama cell keeps the upstream image or the release archive

Given the committed `containers/engines/params/ollama.json` and the four generated Dockerfiles,
When  the source-build guard and the official-image test read them,
Then  `make check-engine-source` reports no finding for any `ollama/*` cell, no Dockerfile starts
`FROM ollama/ollama`, and no install step curls a release tarball.

- **Test:** `tests/test_engine_source_guard.py::test_the_census_matches_the_committed_params` and
  `tests/test_engine_skills.py::test_official_upstream_images_are_used_as_bases`

#### Scenario: each backend compiles its own runner with the shared fat arch list

Given the cuda and rocm variants,
When  the rendered install steps are read,
Then  cuda configures `llama/server` with the `llama_cuda_v13_linux` preset and
`-DCMAKE_CUDA_ARCHITECTURES=75;80;86;89;90;120`, rocm configures it with `GGML_HIP=ON` and
`-DAMDGPU_TARGETS=` the shared fat GPU list, and both install the component `llama-server` under
`{prefix}/{version}`.

- **Test:** `tests/test_engine_skills.py::test_ollama_builds_from_the_pinned_go_source`

### Requirement: The built ollama cell answers its documented flags

When the engine-build workflow builds an ollama image, the build MUST succeed and the image's
binary MUST answer `--version` with the pinned version.

#### Scenario: a built ollama cell reports its version

Given the committed params and an ollama image built by the engine-build workflow,
When  `make build-engine ENGINE=ollama ARCH=<arch>` then
`make test-engine-stage ENGINE=ollama ARCH=<arch> TEST=detect` run,
Then  the build succeeds and `ollama --version` reports `0.40.12`; the cpu image also serves a
model and answers on `/v1/chat/completions`.

- **CI job** `engine-image-ollama-<arch>` -> `make build-engine` + `make test-engine-stage TEST=detect`

### Requirement: The census and the image-shape tests move with the conversion

When four cells change from `prebuilt: true` to source builds, the committed census and the
official-upstream-image test MUST be updated in the same commit.

#### Scenario: the census reads 30 source / 1 prebuilt

Given this change converts ollama's four cells,
When  `tests/test_engine_source_guard.py::test_the_census_matches_the_committed_params` runs,
Then  it reads 30 `prebuilt: false` and 1 `prebuilt: true` cells (31 total), and the single tracked
exception is still `litert/cpu`.

- **Test:** `tests/test_engine_source_guard.py::test_the_census_matches_the_committed_params`
