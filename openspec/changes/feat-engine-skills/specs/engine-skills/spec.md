# engine-skills — spec of record

## ADDED Requirements

### Requirement: every registry engine has exactly one skill
The repo MUST ship one `skills/engines/<id>/SKILL.md` per key in the trending-local-llms
`engines{}` registry, whose `engine:` equals that key. `make skills-validate` MUST fail
when an engine has no skill or a skill names an engine that is not in the registry.

WHEN the skills are validated against the registry
THEN every registry engine maps to exactly one skill and there are no errors.

#### Scenario: all 16 engines are covered
- **Given** the pinned registry snapshot `tests/fixtures/trending-models.json`
- **When** `validate(skills, registry)` runs
- **Then** it returns no errors and the engine names match one-to-one
- **Test:** `tests/test_engine_skills.py::test_every_registry_engine_has_exactly_one_skill`

#### Scenario: a new index engine is reported
- **Given** a registry with an engine that no skill covers
- **When** the skills are validated
- **Then** the error names that engine as having no skill
- **Test:** `tests/test_engine_skills.py::test_validator_reports_a_registry_engine_without_a_skill`

#### Scenario: the make target runs the validator
- **Given** the registry fixture
- **When** `engine_skills.py validate --registry <fixture>` runs (the `make skills-validate` command)
- **Then** it exits 0 and reports `0 error(s)`
- **Test:** `tests/test_engine_skills.py::test_cli_validate_against_fixture_exits_zero`

### Requirement: skill front matter is a strict, stdlib-parseable YAML subset
The runner MUST parse front matter without PyYAML (it runs under the bare `python3`
used by the build script), and the result MUST equal `yaml.safe_load`.

WHEN a SKILL.md is parsed
THEN the stdlib parser and PyYAML agree, and ambiguous YAML is rejected.

#### Scenario: identical to PyYAML
- **Given** every SKILL.md in `skills/engines`
- **When** each is parsed by both parsers
- **Then** the results are equal
- **Test:** `tests/test_engine_skills.py::test_front_matter_parser_matches_pyyaml_for_every_skill`

#### Scenario: unquoted dates are refused
- **Given** front matter `verified: 2026-10-05`
- **When** it is parsed
- **Then** it fails with "unquoted date"
- **Test:** `tests/test_engine_skills.py::test_parser_rejects_unquoted_dates`

### Requirement: build parameters are derived from the detected hardware
A skill MUST declare hardware-derived flags (`hw_flags`) and the runner MUST emit them
only when the parameter was detected: CUDA arch from `nvidia-smi compute_cap`, ROCm
`GPU_TARGETS` from `rocminfo`, CUDA major from `nvcc`. Env seams (`LLAMA_BACKEND`,
`LLAMA_RAM_BYTES`, `LLGENIE_CUDA_ARCH`, `LLGENIE_GPU_TARGETS`, `LLGENIE_CUDA_VERSION`,
`BUILD_JOBS`) override detection for CI and tests.

WHEN a skill is rendered for a machine
THEN its build flags target that machine's GPU and nothing is guessed.

#### Scenario: compute capability becomes the CMake arch
- **Given** compute capabilities 8.9, 8.6, 12.0 and 7.5
- **When** they are converted
- **Then** they become 89, 86, 120 and 75
- **Test:** `tests/test_engine_skills.py::test_cuda_arch_is_derived_from_compute_capability`

#### Scenario: an Ada laptop builds for sm_89
- **Given** the llama.cpp skill and compute capability 8.9
- **When** the cuda cmake flags are rendered
- **Then** they contain `-DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=89 -DGGML_NATIVE=OFF`
- **And** they do not contain `LLAMA_CUBLAS`
- **Test:** `tests/test_engine_skills.py::test_llama_cpp_cuda_build_targets_the_detected_gpu`

#### Scenario: a GPU-less CI container omits the arch flag
- **Given** nvcc present but no visible GPU
- **When** the prism cuda flags are rendered
- **Then** `CMAKE_CUDA_ARCHITECTURES` is absent (CMake default list)
- **Test:** `tests/test_engine_skills.py::test_gpuless_ci_cuda_build_omits_the_arch_flag`

#### Scenario: ROCm uses the detected gfx target
- **Given** an RDNA3 card reporting gfx1100
- **When** the llama.cpp rocm plan is rendered
- **Then** configure has `-DGGML_HIP=ON -DGPU_TARGETS=gfx1100` and HIPCXX comes from hipconfig
- **Test:** `tests/test_engine_skills.py::test_rocm_build_uses_detected_gfx_target_and_hip_env`

#### Scenario: the MLX CUDA extra follows the toolkit
- **Given** CUDA 13.3 and CUDA 12.8 toolkits
- **When** the mlx cuda install is rendered
- **Then** it installs `mlx[cuda13]` and `mlx[cuda12]` respectively
- **Test:** `tests/test_engine_skills.py::test_mlx_cuda_extra_follows_detected_cuda_major`

#### Scenario: env seams override detection
- **Given** `LLAMA_BACKEND=rocm`, `LLGENIE_GPU_TARGETS=gfx1100`, `BUILD_JOBS=6`
- **When** the hardware is detected
- **Then** those values are returned
- **Test:** `tests/test_engine_skills.py::test_detect_hardware_env_seams`

### Requirement: hardware floors block installs with the exact reason
The runner MUST refuse an install whose backend, OS, compute capability, CUDA toolkit,
ROCm gfx target or prerequisite does not match the skill, and name the blocker.

WHEN an engine cannot run on the detected hardware
THEN `check` returns the precise blocker and `install` exits non-zero without running a step.

#### Scenario: TensorFold refuses an RTX 3090
- **Given** TensorFold (needs sm_89) and compute capability 8.6
- **When** the install is checked
- **Then** the blocker reads "compute capability 8.6 < required 8.9"
- **Test:** `tests/test_engine_skills.py::test_compute_capability_floor_blocks_unsupported_gpus`

#### Scenario: SGLang refuses a CUDA 12 toolkit
- **Given** SGLang (CUDA 13 wheels) and CUDA 12.4
- **When** the install is checked
- **Then** the blocker reads "CUDA toolkit 12.4 < required 13.0"
- **Test:** `tests/test_engine_skills.py::test_cuda_toolkit_floor_blocks_old_toolkits`

#### Scenario: the ROCm fork refuses RDNA2
- **Given** exllamav3-rocm and gfx1030
- **When** the install is checked
- **Then** the blocker names gfx1030 as unsupported
- **Test:** `tests/test_engine_skills.py::test_rocm_gfx_allow_list_blocks_unsupported_cards`

#### Scenario: wrong backend and OS
- **Given** TensorRT-LLM on a Mac
- **When** the metal install is checked
- **Then** both the backend and the OS are reported
- **Test:** `tests/test_engine_skills.py::test_unsupported_backend_is_blocked`

### Requirement: only real HTTP servers are installed
Skills MUST declare `servable`. `false` engines are never installed. `via` engines name
host engines (which have skills) that serve the model instead.

WHEN an engine is not an OpenAI-compatible HTTP server
THEN llgenie never installs it and points at a host engine where one exists.

#### Scenario: WebLLM, DFlash2 and MLX-fast
- **Given** the webllm, dflash2 and mlx-fast-bonsai2 skills
- **When** their serving status is read
- **Then** WebLLM is `false` and blocked, DFlash2 is `via` sglang, and MLX-fast is `via` tensorfold and mlx
- **Test:** `tests/test_engine_skills.py::test_non_servable_engines_are_never_installed`

### Requirement: every servable engine exposes llm-local on 127.0.0.1:11434
Each servable skill's launch (plus pre/post-launch and env) MUST bind 127.0.0.1 on the
llgenie port and expose the model as `llm-local` by flag, create, config or symlink.

WHEN any servable skill is rendered
THEN the endpoint contract is visible in its launch.

#### Scenario: launch contract
- **Given** each servable skill rendered for its first backend
- **When** launch, pre/post-launch and env are joined
- **Then** they contain `127.0.0.1`, `11434` and `llm-local`
- **Test:** `tests/test_engine_skills.py::test_every_servable_launch_exposes_llm_local_on_the_port`

### Requirement: engines run from container images, not host venvs
Engines on cuda, rocm, vulkan and cpu MUST be installed only inside their container image (the
container is the isolation) and run with `make run-engine`. Skills MUST NOT create venvs. Python
engines install into the image's Python (`uv pip install --system`). Only Metal, which cannot be
containerized, installs natively, with `uv tool install`. Native `engine-install`/`serve` on an
image backend MUST be refused and point at `make build-engine`. Skills MUST NOT use sudo or pipe a
download into a shell. Release archives MUST be checksum-verified before extraction.

WHEN an engine is installed
THEN it happens in its image (or as a uv tool on Metal), never in a host venv.

#### Scenario: no venv, no sudo, no curl|sh
- **Given** every skill's install steps per backend
- **When** they are scanned
- **Then** there is no venv, sudo or pipe-to-shell; pip uses `--system` on image backends and Metal uses `uv tool install`
- **Test:** `tests/test_engine_skills.py::test_engines_install_into_images_not_venvs`

#### Scenario: native install refused outside Metal
- **Given** vllm on cuda
- **When** a native install is attempted
- **Then** it exits 3 and names `make build-engine ENGINE=vllm`, while mlx on metal is allowed
- **Test:** `tests/test_engine_skills.py::test_native_install_is_refused_except_metal`

#### Scenario: a second install run is a no-op for created state
- **Given** every skill's install steps
- **When** clone steps are read
- **Then** each is guarded (`test -d {src}/.git ||`) so re-running does not fail
- **Test:** `tests/test_engine_skills.py::test_install_steps_are_idempotent`

#### Scenario: skill env values are shell-expanded
- **Given** env values `$(echo expanded)` and `/x:$HOME`
- **When** bash evaluates the env prelude
- **Then** both are expanded, not passed literally
- **Test:** `tests/test_engine_skills.py::test_env_prelude_lets_bash_expand_skill_env`

#### Scenario: Ollama tarball checksum before extract
- **Given** the ollama skill on CUDA
- **When** the steps are ordered
- **Then** `sha256sum -c` against the v0.35.1 release runs before `tar -xf`, and `install.sh` is never used
- **Test:** `tests/test_engine_skills.py::test_ollama_tarball_is_checksum_verified_before_extract`

### Requirement: builds use only generated params; skills are read only by generate-engine-params
Every build path (`make install`, `make build-variant`, `make build-engine`, `make run-engine`,
`make test-engine`, CI) MUST read only the generated, committed files under
`containers/engines/` and run with plain make (no LLM). `scripts/build_llama_server.sh` MUST
take repo, branch, dirs and cmake flags from `scripts/native_build_env.py`, which reads
`params/<id>.json` (`native.<backend>`) plus the detected hardware. `detect_server.py` MUST read
URL/branch from the params.

WHEN skills/ is absent
THEN every build-path tool still works.

#### Scenario: native build env from params
- **Given** `SERVER_ROOT=/srv` and `LLGENIE_CUDA_ARCH=89`
- **When** `native_build_env.py llama.cpp-prism cuda` runs
- **Then** it prints the PrismML repo, branch prism, `/srv/prism-llama.cpp`, its `build-cuda` dir and `-DCMAKE_CUDA_ARCHITECTURES=89`
- **And** the build script evals it, never calls engine_skills.py, and no longer hardcodes `github.com/ggerganov`
- **Test:** `tests/test_engine_skills.py::test_native_build_reads_generated_params_not_skills`

#### Scenario: the build path works with skills/ deleted
- **Given** a copy of the repo without `skills/`
- **When** native_build_env, detect_server and engine_image tag/matrix run
- **Then** all succeed from the generated files
- **Test:** `tests/test_engine_skills.py::test_build_path_works_without_skills`

#### Scenario: upstream clones from ggml-org
- **Given** the upstream tree
- **When** its URL is read through detect_server
- **Then** it is `https://github.com/ggml-org/llama.cpp.git`
- **Test:** `tests/test_detect_server.py::test_tree_urls_are_correct`

#### Scenario: Linux variants run as images from their base images
- **Given** the workflow and the engine-image matrix
- **When** the prism/upstream x cpu/cuda variants are looked up
- **Then** each one is an `engine-image` job built from its own base image, and the old in-container compile job is gone
- **Test:** `tests/test_ci_variant_matrix.py::test_linux_prism_and_stock_variants_are_engine_image_jobs`, `tests/test_ci_variant_matrix.py::test_linux_variants_use_their_base_images`

#### Scenario: every variant has an OpenAI API test stage
- **Given** the engine-image matrix and the macOS variants
- **When** their test stages are read
- **Then** cpu images serve and answer `GET /v1/models` + `POST /v1/chat/completions`, GPU images pass `entrypoint.sh info` + `detect`, and Metal variants answer "hi" natively
- **Test:** `tests/test_ci_variant_matrix.py::test_every_variant_runs_a_test_stage_on_the_openai_api`; CI jobs `engine-image-*` -> `make test-engine` / `make test-engine-image`, `server-variants-mac` -> `make test-serve-variant`

### Requirement: skills are pinned for drift sync
Each skill MUST pin a full 40-hex commit sha and list the upstream files whose change
invalidates it (`upstream_watch`), so #100 can diff them.

WHEN drift sync reads a skill
THEN it has a pin and a watch list.

#### Scenario: pins and watch lists
- **Given** every skill
- **When** `pinned` and `upstream_watch` are read
- **Then** the pin is 40 hex characters and the watch list is non-empty
- **Test:** `tests/test_engine_skills.py::test_skill_pins_are_full_shas_and_watch_lists_exist`

### Requirement: engine parameters are generated per hardware arch and frozen
`make generate-engine-params` MUST render every skill into
`containers/engines/params/<id>.json`, with one variant per containerizable backend (`cpu`, `cuda`, `rocm`, `vulkan`). GPU arch
coverage is a fat build inside it (CUDA `75;80;86;89;90;120`, ROCm `gfx1030…gfx1201;gfx942`). Each variant holds fixed values: in-image paths, the pinned checkout, arch flags,
base image, apt packages, env, launch, health and docker run args. A file MUST be rewritten only
when its rendered parameters differ. `make check-engine-params` MUST fail on stale files.

WHEN a skill changes
THEN regenerating rewrites only the affected params file, and CI fails until it is committed.

#### Scenario: committed params are fresh
- **Given** the current skills and the committed params
- **When** the params are regenerated in check-only mode
- **Then** nothing differs
- **Test:** `tests/test_engine_skills.py::test_committed_engine_params_match_the_skills`

#### Scenario: one variant per backend
- **Given** the prism (compiled) and vllm (wheel) skills
- **When** their params are generated
- **Then** prism has exactly cuda, rocm, vulkan and cpu, and vllm has cuda, rocm and cpu
- **Test:** `tests/test_engine_skills.py::test_params_have_one_variant_per_backend`

#### Scenario: a variant is hard-coded and self-contained
- **Given** prism's cuda variant
- **When** it is inspected
- **Then** it has the quoted `'-DCMAKE_CUDA_ARCHITECTURES=75;80;86;89;90;120'`, the pinned sha, `/opt/llgenie/src` paths, no host paths, and `--gpus all`
- **Test:** `tests/test_engine_skills.py::test_frozen_variant_is_hardcoded_and_self_contained`

#### Scenario: one rocm image covers all common gfx targets
- **Given** the Prism fork's rocm variant (no official image, so it compiles)
- **When** its configure step is read
- **Then** `'-DGPU_TARGETS=gfx1030;…;gfx942'` is one quoted argument
- **Test:** `tests/test_engine_skills.py::test_rocm_variant_compiles_all_common_gfx_targets`

#### Scenario: CI checks freshness
- **Given** the CI unit job
- **When** its steps are read
- **Then** `make check-engine-params` runs
- **Test:** `tests/test_engine_skills.py::test_ci_checks_params_are_fresh`

### Requirement: build-engine builds only from the frozen params for the machine's arch
`make build-engine ENGINE=<id> [ARCH=<variant>]` MUST build the image from the committed
params variant only (never a skill). The variant is the detected GPU arch when generated, else
`<backend>-portable`. The tag MUST hash the frozen variant plus Dockerfile, entrypoint and runner,
so an unchanged engine is never rebuilt. The image MUST `EXPOSE 11434`, run
`entrypoint.sh` (serve via `engine_runner.py serve params.json`), and serve the OpenAI API as
`llm-local`. `make run-engine` publishes it on `127.0.0.1:$(PORT)`.

WHEN build-engine runs twice with unchanged params
THEN the second run is a no-op, and run-engine exposes `http://127.0.0.1:<PORT>/v1`.

#### Scenario: the image is the backend
- **Given** prism's params
- **When** images are picked for sm_89, sm_61 and gfx1100
- **Then** they are cuda, cuda (with a note that sm_61 is not compiled in) and rocm
- **Test:** `tests/test_engine_skills.py::test_variant_is_the_backend`

#### Scenario: the build never reads a skill
- **Given** the Dockerfile, entrypoint and image driver
- **When** they are read
- **Then** the build copies `params.json` and runs `engine_runner.py install params.json`, and exposes 11434 with the entrypoint
- **Test:** `tests/test_engine_skills.py::test_build_engine_reads_only_the_frozen_params`

#### Scenario: one make target per engine x arch
- **Given** `build-engine-vllm-cuda`, `build-engine-llama.cpp-prism-rocm` and `build-engine-llama.cpp-laurentzuijdwijk-vulkan`
- **When** make dry-runs them
- **Then** each calls `build-engine` with the engine (split on the last dash) and the arch
- **Test:** `tests/test_engine_skills.py::test_per_engine_arch_make_targets_resolve_engine_and_arch`

#### Scenario: no rebuild unless parameters change
- **Given** prism's cuda params
- **When** it is tagged twice, and once with a changed launch flag
- **Then** the first two tags are equal and the changed one differs
- **Test:** `tests/test_engine_skills.py::test_image_tag_changes_only_when_the_frozen_variant_changes`

#### Scenario: the runner binds host, port and model at run time
- **Given** a frozen plan whose launch uses `{model}`, `{host}`, `{port}` and a shell-expanded env
- **When** `engine_runner.serve_plan` runs it
- **Then** the placeholders are bound, the env is expanded, and the server becomes ready
- **Test:** `tests/test_engine_skills.py::test_runner_serves_from_a_frozen_plan`

### Requirement: one generated Dockerfile per engine x arch on the best base image
`make generate-engine-params` MUST also write `containers/engines/dockerfiles/<id>/Dockerfile.<arch>`
for every params variant, fully resolved (no build args), `EXPOSE 11434`, entrypoint
`entrypoint.sh`. When the engine publishes an official image, it MUST be the base and the engine
MUST NOT be reinstalled on top (vllm/vllm-openai[-cpu|-rocm], ollama/ollama[-rocm], lmsysorg/sglang,
nvcr.io tensorrt-llm). Compiled engines MUST build on the devel base and ship on the slim runtime
base, copying only the build output. `make build-engine` MUST build exactly that file.

WHEN params are generated
THEN each engine x arch has its Dockerfile, on the official image where one exists.

#### Scenario: a Dockerfile per variant, in sync with the generator
- **Given** the committed params
- **When** each variant's Dockerfile is read
- **Then** it equals the generator output, exposes 11434 and uses the entrypoint
- **Test:** `tests/test_engine_skills.py::test_one_generated_dockerfile_per_engine_arch`

#### Scenario: official images are the base
- **Given** the llama.cpp, vllm, ollama, sglang and tensorrt-llm Dockerfiles
- **When** their FROM lines are read
- **Then** they are the engines' official images (llama.cpp: `ghcr.io/ggml-org/llama.cpp:server[-cuda|-rocm|-vulkan]` pinned by digest), and nothing is installed on top
- **Test:** `tests/test_engine_skills.py::test_official_upstream_images_are_used_as_bases`

#### Scenario: no image starts from a bare distro
- **Given** every generated Dockerfile
- **When** its first FROM is read
- **Then** it is an official/upstream image (vllm, ollama, ggml-org, lmsysorg, NGC, rocm/pytorch) or the shared llgenie base, never ubuntu/nvidia-cuda/rocm-dev directly
- **Test:** `tests/test_engine_skills.py::test_every_image_uses_an_official_or_shared_base`

#### Scenario: compiled engines build on the shared base and ship slim
- **Given** prism's cuda Dockerfile and `containers/engines/base/Dockerfile.cuda`
- **When** their stages are read
- **Then** the build stage is the shared base (cuda devel + toolchain, no per-engine apt), and the run stage is `cuda:13.0.2-runtime` copying only `build-cuda/bin`
- **Test:** `tests/test_engine_skills.py::test_compiled_engines_build_on_the_shared_base_and_ship_slim`

#### Scenario: registry cache and published-image reuse
- **Given** the image driver
- **When** its build path is read
- **Then** it uses buildx `--cache-from`/`--cache-to` (mode=max) on GHCR and pulls an already-published tag instead of rebuilding
- **Test:** `tests/test_engine_skills.py::test_builds_use_a_registry_cache_and_reuse_published_images`

#### Scenario: pushes go only to the registry
- **Given** `LLGENIE_REGISTRY=ghcr.io/asimov-agent` and PUSH
- **When** an image is built
- **Then** buildx tags and pushes only `ghcr.io/asimov-agent/<tag>` (never a bare tag that would go to Docker Hub), with the registry cache in and out
- **Test:** `tests/test_engine_skills.py::test_push_targets_only_the_registry_tag`

#### Scenario: build-engine builds the generated file only
- **Given** the image driver
- **When** it is read
- **Then** it builds `spec["dockerfile"]` with the frozen params, and there is no shared hand-written Dockerfile
- **Test:** `tests/test_engine_skills.py::test_build_engine_uses_the_generated_dockerfile_only`

### Requirement: CI builds, pushes and tests the images in parallel
The CI `engine-matrix` job MUST compute the engine x arch job list with
`make -s list-engine-images CI=1 JSON=1`. `engine-image` MUST run one parallel job per entry with
`make build-engine ENGINE=… ARCH=…`, then the post-build test: `make test-engine` for the cpu
variants (the OpenAI SDK test in `llgenie/test`, built in the same job: `/v1/models` lists
`llm-local`, `/v1/chat/completions` answers "hi" on the published port) and
`make test-engine-image` for GPU variants (`tests/test_engine_version.py` in `llgenie/test`
with the host docker socket: the binary prints its version). Builds MUST NOT need a
developer laptop. `make ci-engine-images` reports the CI build status.

WHEN the workflow runs
THEN every engine x CI arch is built and tested in parallel, and the cpu images answer as llm-local.

#### Scenario: matrix generated from params, built and tested via make
- **Given** the CI workflow and `engine_image.matrix(ci=True)`
- **When** the jobs and steps are read
- **Then** the matrix comes from make, `engine-base` publishes the shared bases first, each job builds the test image, runs build-engine and its post-build test, and the key engine x backend pairs are present
- **Test:** `tests/test_engine_skills.py::test_ci_builds_every_engine_arch_in_parallel_from_make`

#### Scenario: each smoked engine has a tiny model
- **Given** the smoked engines
- **When** `engine_smoke.pick_format` reads each skill's formats
- **Then** a tiny ungated test model exists for that format
- **Test:** `tests/test_engine_skills.py::test_every_smoked_engine_has_a_tiny_test_model`

#### Scenario: an image answers on the published port
- **Given** a cpu image built by `make build-engine` in CI
- **When** `make test-engine ENGINE=<id> ARCH=cpu` runs
- **Then** the container becomes ready, `/v1/models` on 127.0.0.1:<port> lists llm-local and "hi" gets a reply
- **Test:** CI jobs `engine-image-<engine>-cpu` -> `make test-engine ENGINE=… ARCH=cpu`

#### Scenario: Metal engines install natively on macOS
- **Given** the macos-14 runner
- **When** `make engine-smoke ENGINE=<ollama|mlx> BACKEND=metal` runs
- **Then** the skill installs the engine and llm-local answers
- **Test:** CI jobs `engine-smoke-<engine>-metal` -> `make engine-smoke ENGINE=… BACKEND=metal`


### Requirement: make install runs engines only through their images
`make install` MUST NOT build an engine on the host. It MUST detect the host backend
(cuda, rocm, vulkan or cpu; `LLAMA_BACKEND` / `ARCH=` mock it) and PULL only that
backend's published, CI-tested images from `LLGENIE_REGISTRY` (default
`ghcr.io/asimov-agent`); an engine without one falls back to its cpu image. It builds an
image only with `BUILD=1` and otherwise fails loudly when an image is not published. By
default it installs the llama.cpp core (stock + Prism); `ENGINES=all` installs every engine,
and any other engine is pulled the first time `llgenie --pick/--engine` selects it
(`install_engine_launchers.py --ensure`). It MUST write a start script per installed engine into `~/bin`
(`llgenie-engine-<id>`) plus two container shims that take the llama-server CLI:
`~/bin/llama-server` (stock llama.cpp image) and `~/bin/prism-server` (Prism image), each
running that image's own llama-server binary (`/app/llama-server` in the ggml-org image,
`build-<arch>/bin/llama-server` in the Prism image). `llama_serve.resolve_llama_server`
uses `prism-server` on prism cards (<= 24 GB, `LLAMA_SERVER_TREE`) and `llama-server`
otherwise. Every start script and both shims MUST print their engine version through
their image.

WHEN `make install` finishes
THEN every `~/bin/llgenie-engine-*` script answers `--version` from its container.

#### Scenario: start scripts are written for every engine with an image for this host
- **Given** the generated params and a host backend
- **When** `scripts/install_engine_launchers.py` runs
- **Then** each engine with a variant for the backend (cpu fallback) gets an executable `llgenie-engine-<id>` that docker-runs its image
- **Test:** `tests/test_engine_skills.py::test_install_writes_container_start_scripts`

#### Scenario: install pulls only this backend's published images
- **Given** each backend cpu, cuda, rocm, vulkan
- **When** `install_engine_launchers.install(..., build=False)` runs
- **Then** only that backend's image variant (cpu fallback) is requested, nothing is built, an unpublished image fails the install, and the default set is the llama.cpp core
- **Test:** `tests/test_engine_skills.py::test_install_pulls_only_the_images_for_this_backend`, `tests/test_engine_skills.py::test_install_fails_loudly_when_an_image_is_not_published`, `tests/test_engine_skills.py::test_install_writes_container_start_scripts`, `tests/test_engine_skills.py::test_make_install_defaults_pull_from_the_published_registry`

#### Scenario: llgenie pulls the picked engine on first use
- **Given** `llgenie --pick/--engine` chose an engine that is not installed
- **When** it serves the model
- **Then** it runs `install_engine_launchers.py --ensure <id> --arch <variant>`, which pulls only that engine's image for this backend and writes its start script
- **Test:** `tests/test_engine_skills.py::test_ensure_pulls_one_engine_on_first_use`

#### Scenario: one shim per llama.cpp tree, named after its server
- **Given** an install with the llama.cpp and llama.cpp-prism images
- **When** the shims are written and llgenie resolves its server
- **Then** `~/bin/llama-server` runs the stock image and `~/bin/prism-server` the Prism image, each with its image's real binary path and a per-port container `llgenie-<shim>-<port>`; a prism card resolves `prism-server`, an upstream card `llama-server`
- **Test:** `tests/test_engine_skills.py::test_install_writes_container_start_scripts`, `tests/test_engine_skills.py::test_llama_server_shim_uses_the_images_real_binary_path`, `tests/test_llama_ai.py::test_resolve_picks_prism_server_on_a_prism_card`

#### Scenario: make test-built-engine checks every start script
- **Given** installed start scripts
- **When** `make test-built-engine` runs
- **Then** each script's `--version` must exit 0 and print the engine version, else the target fails
- **Test:** `tests/test_engine_skills.py::test_install_writes_container_start_scripts`

#### Scenario: the test image holds no inference server
- **Given** `containers/test/Dockerfile`
- **When** the image is built
- **Then** it has python, pytest, the locked deps, hf and the docker CLI, and no llama-server; tests start the engine images through the host docker socket
- **Test:** CI jobs `install` / `cpu-health` / `top-tier` -> `make test-install-ci` / `make test-health` / `make test-top-tier-serve-ci` (all through `$(ENGINE_TEST_RUN)`)

#### Scenario: CI runs the real make install end to end
- **Given** a clean ubuntu runner with docker and the test image
- **When** the `install` job runs `make test-install-ci ARCH=cpu` (inside the test container, host docker socket mounted)
- **Then** `make install` pulls/builds every engine image with a cpu variant and writes the start scripts, `make test-built-engine` passes, the install tests pass, llgenie answers "hi" through the container `~/bin/llama-server`, and `make uninstall` removes every installed file
- **Test:** `tests/test_ci_variant_matrix.py::test_install_ci_runs_make_install_and_make_uninstall`; CI job `install` -> `make test-install-ci`

### Requirement: images are pushed only after their tests pass, on every push run
The CI engine-image job MUST build without pushing, run its post-build test, and only
then publish with `make push-engine`. For now (#101) every `push` run publishes, feature
branches included, to the repo's own GHCR (`ghcr.io/<owner>/llgenie/<name>`), so the
published-image matrix can test a branch's images before merge. `pull_request` runs have a
read-only token and never push.

WHEN an engine-image job runs on a push and its tests pass
THEN the image is pushed to GHCR as `<name>:<pinned-hash-arch>` and `<name>:<arch>`.

#### Scenario: push step is gated on a push run and on passed tests
- **Given** the CI workflow
- **When** the engine-image steps are read
- **Then** `make build-engine` has no PUSH, the test step precedes `make push-engine`, and the push step runs only when PUBLISH (`github.event_name == 'push'`) is set
- **Test:** `tests/test_engine_skills.py::test_ci_builds_every_engine_arch_in_parallel_from_make`

### Requirement: make uninstall undoes the container install
`make uninstall` MUST remove `~/bin/llgenie`, `~/bin/llgenie.py`, every `llgenie-engine-*`
start script and the `~/bin/llama-server` shim that `make install` wrote, and stop running
`llgenie-*` engine containers. It MUST NOT remove files it did not write, models, the venv,
the repo, or any source tree. Engine images stay as a cache unless `PURGE_IMAGES=1`.

WHEN `make uninstall` runs after `make install`
THEN only the installed files are gone and no llgenie engine container is running.

#### Scenario: only generated files are removed
- **Given** an install into a bin dir that also holds a foreign `llgenie-engine-mine` and `other-tool`
- **When** `install_engine_launchers.py --uninstall` runs
- **Then** the generated start scripts and the shim are gone and both foreign files remain
- **Test:** `tests/test_ci_variant_matrix.py::test_uninstall_removes_only_what_install_wrote`, `tests/test_ci_variant_matrix.py::test_uninstall_removes_install_artifacts_and_not_repo_source`; CI job `install` -> `make test-install-ci` (asserts the files are gone, a foreign file stays, and no `llgenie-` container runs)

### Requirement: every published image is tested again as a separate matrix stage (issue #102)
After `engine-image` built, tested and pushed every image (every push run, feature
branches included, default for now: #101), the SECOND matrix `engine-published-test`
(one job per container image, `test-published-<engine>-<arch>`) MUST test each one again
as published: on a fresh runner, with no build and no cache, it pulls the pinned tag from
GHCR, checks it has the same digest as the moving `:<arch>` tag, checks the binary
version, STARTS the container and requires a "hi" answer on `/v1/chat/completions`
(GPU images run without GPU devices and fall back to CPU; no self-hosted runner), and
installs it from the registry only (`make engine-launchers`, never builds) + `make test-built-engine`.

WHEN an image was pushed to GHCR by a push run
THEN the published-image matrix pulls that exact image, runs its container and chats with it.

#### Scenario: published-image matrix stage
- **Given** the CI workflow
- **When** the `engine-image` and `engine-published-test` jobs are read
- **Then** `engine-image` tests before it pushes, `engine-published-test` needs it, runs on every push run over the same matrix (job names `test-published-<engine>-<arch>`) with read-only package access and a GHCR login, never builds, and runs `make test-published-engine` (version + container "hi") + registry-only install + `make test-built-engine`
- **Test:** `tests/test_engine_skills.py::test_published_images_are_tested_again_as_a_separate_matrix_stage`

#### Scenario: only the published image is accepted
- **Given** a pinned tag and its moving `:<arch>` tag in the registry
- **When** `engine_image.py pull-published` runs
- **Then** the local copy is removed first, the registry tag is pulled, a digest mismatch or a missing registry fails
- **Test:** `tests/test_engine_skills.py::test_pull_published_refuses_a_local_build_and_a_digest_mismatch`

### Requirement: the native macOS smoke binds the run port and needs no docker
The native (Metal) engine smoke MUST render the skill env with the run's host/port, and MUST run
`tests/test_engine_runs.py` with uv and the locked deps (`tools/requirements*.txt`), because the
macOS runner has no docker.

WHEN the macOS smoke serves an engine on a free port
THEN the engine listens on that port and the endpoint test runs without docker.

#### Scenario: native smoke binds the run port and needs no docker
- **Given** the ollama skill and a run on port 49200
- **When** the native plan is rendered and the smoke driver is read
- **Then** `OLLAMA_HOST` is `127.0.0.1:49200` and the native harness uses `uv run --with-requirements`, not the test image
- **Test:** `tests/test_engine_skills.py::test_native_plan_binds_skill_env_to_the_requested_port`, `tests/test_engine_skills.py::test_native_smoke_runs_the_endpoint_test_without_docker`; CI jobs `engine-smoke-ollama-metal`, `engine-smoke-mlx-metal`

### Requirement: GPU images answer on CPU when no GPU is present
Hosted runners have no GPU. A GPU image (cuda, rocm, vulkan) of an engine with a CPU
fallback MUST still start and answer "hi" on `/v1/chat/completions` when run without GPU
devices (`engine_smoke.py --no-gpu`). This is the endpoint test of those published GPU
images; no self-hosted runner is used (GPU-only engines: see below).

WHEN a published GPU image is started without GPU devices
THEN `/v1/models` lists `llm-local` and the chat completion answers.

#### Scenario: published GPU image is chatted with on a GPU-less runner
- **Given** `make test-published-engine ENGINE=<id> ARCH=<cuda|rocm|vulkan>`
- **When** the recipe runs
- **Then** it pulls the published image, runs `make test-engine-image` (version), then `engine_smoke.py --image --no-gpu` (run args reduced to `--shm-size`) and the endpoint test
- **Test:** `tests/test_engine_skills.py::test_every_published_image_is_started_and_answers_hi`

### Requirement: container runs have room for engine shared memory and RAM
Every engine container MUST get `--shm-size 2g` (docker's 64 MiB `/dev/shm` stops vLLM),
and vLLM on CPU MUST size its KV cache with `VLLM_CPU_KVCACHE_SPACE` instead of
`--gpu-memory-utilization` (which reserves that share of system RAM on CPU).

WHEN vllm/cpu is started by `make test-engine`
THEN it starts, lists `llm-local` and answers "hi".

#### Scenario: vllm cpu launch and run args
- **Given** the generated vllm params and `engine_skills.RUN_ARGS`
- **When** they are read
- **Then** the cpu launch has no `--gpu-memory-utilization`, its env sets `VLLM_CPU_KVCACHE_SPACE`, cuda keeps 0.90, and cpu/cuda/vulkan run args carry `--shm-size`
- **Test:** `tests/test_engine_skills.py::test_vllm_cpu_does_not_reserve_90_percent_of_ram_and_gets_shm`

### Requirement: ROCm source builds use a base and arch list their build accepts
exllamav3-rocm, sglang and freetoken compile on ROCm. Each MUST build on the pinned
`rocm/pytorch:rocm7.2.4_ubuntu24.04_py3.12_pytorch_release_2.10.0` base (ROCm >= 7.2.4 as
exllamav3 requires; the torch headers sglang's `-std=c++17` AOT kernels compile against),
install into that base's python (`python3 -m pip`, constraints from its torch), and pass a
GPU arch list in the separator and range the project accepts (exllamav3: RDNA3/3.5/4,
comma-separated; freetoken: RDNA3/4). FreeToken's ROCm build exists only after v0.1.3, so it
is pinned to a commit on main; sglang follows upstream `docker/rocm.Dockerfile`
(`pyproject_rocm.toml` AOT kernels for `gfx942`, `pyproject_other.toml [srt_hip,diffusion_hip]`,
rustc/cargo 1.91 for the multimodal extension).

WHEN the ROCm images are generated
THEN their base, arch lists and install steps are the ones above.

#### Scenario: ROCm bases and arch lists
- **Given** the generated rocm params of exllamav3-rocm, sglang and freetoken
- **When** they are read
- **Then** all three use the pinned rocm/pytorch 7.2.4 base (no `:latest`), freetoken is not cloned at the v-tag and installs torch 2.11 from the PyTorch ROCm 7.2 index
- **Test:** `tests/test_engine_skills.py::test_rocm_source_builds_pin_a_base_their_build_accepts`

### Requirement: make install is tested last, against the published images, per backend
After `engine-published-test`, the CI matrix `install-published` (cpu, cuda, rocm, vulkan)
MUST run the real `make install` on a clean runner with the backend mocked through
`LLAMA_BACKEND` (GPU images on CPU via `LLGENIE_NO_GPU=1`): install pulls only that
backend's published images (nothing built), llgenie answers "hi" through `llama-server`
(upstream tree) and `prism-server` (Prism tree) from the right image's container,
`llgenie --pick --auto --engine <e> --model-file <m>` pulls the picked engine on first use
and its container answers "hi", and `make uninstall` leaves no file or container.

WHEN the images of a push run are published and re-tested
THEN `make install` is proven per backend against exactly those images.

#### Scenario: install-published matrix
- **Given** the CI workflow and `make test-install-published BACKEND=<b>`
- **When** they are read
- **Then** `install-published` needs `engine-published-test`, runs per backend on every push run with a GHCR login and never builds, and the make target mocks the backend and runs `tests/test_install_published.py`
- **Test:** `tests/test_engine_skills.py::test_install_published_is_the_last_stage_per_mocked_backend`; CI jobs `install-published-<backend>` -> `make test-install-published BACKEND=<backend>`

### Requirement: disabled engine images are left out everywhere until fixed (issue #103)
An engine x arch image that fails to build or does not finish in CI MUST be listed in
`engine_image.DISABLED` with its tracking issue. A disabled image is not a CI job
(`matrix(ci=True)`), is never pulled by `make install` or `--ensure` (the engine falls back
to its cpu image, or is skipped), and is never offered by `llgenie --pick`. Currently:
llama.cpp-laurentzuijdwijk/cuda, exllamav3-rocm/rocm, llama.cpp-prism/cuda,
llama.cpp-prism/rocm (issue #103).

WHEN an image is in `DISABLED`
THEN no CI job, install or pick uses it.

#### Scenario: disabled images are not built, installed or offered
- **Given** `engine_image.DISABLED`
- **When** the CI matrix, `install_engine_launchers.variant_for` and `model_engine_pick.rank_engines` are evaluated for every backend
- **Then** none of them yields a disabled engine x arch; the CI matrix is every params variant minus the disabled ones
- **Test:** `tests/test_engine_skills.py::test_ci_builds_every_engine_arch_in_parallel_from_make`, `tests/test_engine_skills.py::test_install_pulls_only_the_images_for_this_backend`, `tests/test_model_engine_pick.py::test_disabled_images_are_never_offered`, `tests/test_ci_variant_matrix.py::test_linux_prism_and_stock_variants_are_engine_image_jobs`

### Requirement: GPU-only engines get the version test on GPU-less runners
Only engines whose GPU image falls back to CPU without GPU devices (`engine_image.CPU_FALLBACK`:
the llama.cpp family and Ollama) are chat-tested on their published cuda/rocm/vulkan image.
vLLM, SGLang, TensorRT-LLM, FreeToken, mlx (cuda) and TensorFold refuse to start without a GPU
(CI run 37407553595), so their published GPU images get the binary-version test and their
cpu images (where they exist) the "hi" chat. The registry-only install step of the published
stage runs with `LLGENIE_NO_GPU=1` (no CDI spec on the runner).

WHEN `make test-published-engine` runs for a GPU-only engine's GPU image
THEN it pulls it, checks digest and version, and skips only the chat with a printed reason.

#### Scenario: chat-testable engine x arch
- **Given** `engine_image.chat_testable`
- **When** it is asked for each engine x arch
- **Then** cpu images and the CPU_FALLBACK engines' GPU images are chat-tested; the GPU-only engines' GPU images are not
- **Test:** `tests/test_engine_skills.py::test_only_engines_with_a_cpu_fallback_are_chat_tested_on_gpu_images`, `tests/test_engine_skills.py::test_published_install_step_runs_gpu_images_on_cpu`
