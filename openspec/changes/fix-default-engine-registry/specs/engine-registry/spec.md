## ADDED Requirements

### Requirement: engine images default to the published registry
llgenie MUST pull a picked engine's image from `ghcr.io/asimov-agent` when `LLGENIE_REGISTRY` is
not set, whether or not it runs through make. `LLGENIE_REGISTRY` MUST override the default, and an
empty `LLGENIE_REGISTRY` MUST keep meaning local images only.

#### Scenario: the default without make
- **Given** a Python process with no `LLGENIE_REGISTRY` in its environment
- **When** `engine_image` is imported
- **Then** its registry is `ghcr.io/asimov-agent`; `LLGENIE_REGISTRY=ghcr.io/AndyHolst/` gives `ghcr.io/andyholst`; `LLGENIE_REGISTRY=` gives `""`; the Makefile exports the same default
- **Test:** `tests/test_engine_skills.py::test_engine_images_default_to_the_published_registry_without_make`

#### Scenario: first-use pull with no LLGENIE_REGISTRY (live GHCR)
- **Given** no local llama.cpp cpu image and no `LLGENIE_REGISTRY`
- **When** llgenie's first-use install (`install_engine_launchers.py --ensure llama.cpp --arch cpu`) runs
- **Then** it pulls `ghcr.io/asimov-agent/<tag>`, writes the start script with that tag, and never prints "no LLGENIE_REGISTRY"
- **Test:** `tests/test_install_published.py::test_first_use_pull_works_without_llgenie_registry_live`

### Requirement: Strata's launch line is accepted by its server and serves llm-local
The Strata launch MUST pass only arguments Strata's `serve/server.py` accepts and MUST expose the
model as `llm-local` through the config's `aliases`.

#### Scenario: the image's launch line runs against Strata's real server.py
- **Given** Strata's source at the pinned commit, its pinned server packages and a setup-style config
- **When** the image's launch line runs (the mock engine instead of the GPU engine)
- **Then** the server starts, `/v1/models` lists `llm-local`, and a chat to `model=llm-local` answers with `model: llm-local`; the old `--model-alias` line fails with "unrecognized arguments"
- **Test:** `tests/test_strata_download.py::test_launch_line_is_accepted_by_strata_server_and_serves_llm_local`

### Requirement: the Strata engine in the image runs on AVX2 CPUs and is reused by setup
The Strata image MUST compile the engine portable (`STRATA_PORTABLE=ON`: no AVX-512 outside
Strata's runtime-dispatched kernels) and MUST ship `engine/BUILD.json` that setup.py accepts, so
setup does not recompile the engine at start.

#### Scenario: the image's engine on an AVX2 CPU
- **Given** the built Strata image
- **When** `ggml_cpu_init` is disassembled and setup's own source hash is compared with `engine/BUILD.json`
- **Then** `ggml_cpu_init` has no zmm instruction and setup.py's `source_hash(ENGINE_SOURCES)` equals the stamp's `src`
- **Test:** `tests/test_engine_version.py::test_strata_engine_runs_on_avx2_cpus_and_setup_reuses_it` (CI post-build stage, `make test-engine-image ENGINE=strata`)
