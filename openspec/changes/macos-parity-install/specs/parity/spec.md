# macos-parity-install

## ADDED Requirements

### Requirement: the same pipeline on Linux and macOS, diverging only on the engine matrix
CI MUST run one pipeline twice in parallel, on a Linux and a macOS runner, with the same
`make` commands and asserts. The only divergences MUST be (1) the test environment: Linux
pulls `llgenie/test` and runs the stages in that container; macOS runs the same stages in the
Python 3.11 gguf venv and MUST NOT run a Docker GitHub Action, and (2) the per-OS engine set:
Linux builds/tests the container engine images it supports; macOS supports the native-Metal
engines, which CI does not run (GitHub's macOS runners have no Metal GPU) and which are proven
with `make ci-engines BACKEND=metal` on an Apple-Silicon host. macOS never runs an inference
server in a container, so CI MUST NOT have a macOS published-image stage. No macOS-only make
target or CI job may exist.

WHEN a CI run starts
THEN the linux and the macos pipeline run the same jobs through the same make commands,
     diverging only where the engine matrix differs.

#### Scenario: linux and macos call the same pipeline
Given  ci.yml, pipeline.yml, published.yml and the Makefile,
When   the callers of each shared pipeline are read,
Then   a push starts one run on every branch,
And    linux and macos call pipeline.yml on ubuntu-latest and macos-15-intel,
And    the pipeline install job runs `make ci-install` on both OSes: it prepares the environment, then runs `make install`, `$HOME/bin/llgenie --dry` and `make uninstall` as separate make targets; macOS runs them in the Python 3.11 venv and never runs a container; Linux runs `make install`, the dry run and `make uninstall` inside the test container,
And    a macOS failure fails the run, the same as a Linux failure,
And    no macOS-only make target or job exists.
- **Test:** `tests/test_macos_install.py::test_linux_and_macos_run_the_same_pipeline`

#### Scenario: macOS runs the Linux pipeline file job for job (no combined jobs)
Given  ci.yml and pipeline.yml,
When   the callers of pipeline.yml are read,
Then   linux and macos both call pipeline.yml, only the runner label differs,
And    pipeline-macos.yml (the combined three-job layout of issue #117) no longer exists,
And    each of the 10 jobs runs one `make ci-<job>` target, none twice, none with an `if:`.
- **Test:** `tests/test_ci_images.py::test_macos_runs_the_linux_pipeline_file_job_for_job`

#### Scenario: macOS has no published-image stage and no native-engine CI job
Given  ci.yml and published.yml,
When   the jobs and their runners are read,
Then   the only macOS job is the shared `macos` pipeline,
And    there is no `macos-published` job (macOS never runs an engine container, so it has no published images to test),
And    there is no `native-engine-macos-arm64` job (the macOS runners have no Metal GPU),
And    published.yml is Linux only.
- **Test:** `tests/test_macos_install.py::test_macos_has_no_published_image_or_native_engine_ci_job`

### Requirement: every make command executes its corresponding Python script
Every top-level `make` target that does engine/install/test work MUST be a thin shell entrypoint
that runs a corresponding Python script (no hidden `_install` internal command API). The same
script MUST run on both OSes: inside the docker test image on Linux, inside the 3.11 venv (and
natively for Metal) on macOS.

WHEN a make target runs
THEN the engine/install/test logic lives in a Python script that the target invokes.

#### Scenario: the make target delegates to a python script
Given  the install target and the engine-launch test target,
When   their recipes are read,
Then   each runs a python script from scripts/ (never a second shell implementation).
- **Test:** `tests/test_macos_install.py::test_pure_make_surface_runs_the_python_script`

### Requirement: `make install` per engine, per environment
At the end of the pipeline, each OS MUST run `make install` **for each engine it supports, in
that engine's own environment**, and prove the installed engine works (start script reports the
engine version; where the OS/environment can serve, the engine answers on the OpenAI endpoint).
The per-OS install-prove set MUST be the engines that OS supports (Linux: container images;
macOS: native-Metal engines). Hard-fails if any supported engine is not proven.

WHEN the per-OS engine install proof runs
THEN each supported engine is made installable/proven in its own environment, on that OS.

#### Scenario: linux proves each container engine it supports
Given  a Linux runner whose supported engine set is the container engine images,
When   the per-engine install proof runs `make install` for each supported engine,
Then   every start script reports the engine version and the container engine answers "hi",
And    no supported engine is skipped.
- **Test:** CI jobs `linux-published / install-published-<backend>` -> `make ci-engines BACKEND=<cpu|cuda|rocm|vulkan>` (-> `make test-install-published`)

#### Scenario: macos proves each native-Metal engine it supports
Given  an Apple-Silicon macOS host whose supported engine set is the native-Metal engines
       (issue #114; Metal cannot run in a container),
When   the per-engine install proof runs `make install` for each supported native engine,
Then   every native engine is installed in its own environment and serves on Metal,
And    no supported engine is skipped.
- **Test:** `make ci-engines BACKEND=metal` on an Apple-Silicon host, no CI job (-> `make test-native-engines` = `tests/test_native_engines.py::test_each_native_engine_installs_and_answers_hi_on_metal`, + `test-native-engine`, `test-interactive-tensorfold-ci`, `test-native-engine-light`)

#### Scenario: a published port is reached from inside the test container
Given  the published-install test runs inside the test container and the engine port is published on the host,
When   the test waits for `/v1/models` and posts `"hi"`,
Then   it talks to `host.lima.internal` or `host.docker.internal` (whichever resolves), not the container's own `127.0.0.1`,
And    on the host itself it talks to `127.0.0.1`.
- **Test:** `tests/test_install_published.py::_probe_host` (used by `_chat`); CI jobs `linux-published / install-published-<backend>`

#### Scenario: a host too small for the light TensorFold model names the budget
Given  TensorFold's plan refuses the light checkpoint because the host RAM is too small,
When   `make test-native-engine-light` runs,
Then   the plan output contains `need more than` and the start script exits with `do not fit`,
And    the test does not require a phrase TensorFold does not print.
- **Test:** `tests/test_native_engine_light.py` via `make test-native-engine-light`

#### Scenario: one engine stage, only BACKEND differs
Given  the Linux published install job and the Makefile,
When   the engine-install step is read,
Then   it runs `make ci-engines BACKEND=<backend>` (an Apple-Silicon host runs the same target with `BACKEND=metal`),
And    the target runs `scripts/ci_engines.py`, which maps BACKEND to that OS's make targets,
And    every stage of the row runs and any failing stage fails the run.
- **Test:** `tests/test_macos_install.py::test_engine_stage_is_one_make_target`, `tests/test_macos_install.py::test_ci_engines_plans_the_backends_engine_matrix`, `tests/test_macos_install.py::test_ci_engines_runs_every_stage_and_fails_when_one_fails`, `tests/test_macos_install.py::test_ci_engines_rejects_an_unknown_backend_and_metal_off_apple_silicon`

#### Scenario: every native-Metal engine is in the macOS matrix
Given  the servable engine skills with a `metal` backend and a metal install
       (`model_engine_pick.metal_engines()`: litert, llama.cpp, llama.cpp-prism, mlx, ollama, tensorfold),
When   the macOS engine matrix is read,
Then   each one is installed natively and served on Metal (tiny model) or by its named serve target,
And    llama.cpp and llama.cpp-prism are BUILT natively by their skill (cmake `-DGGML_METAL=ON`).
- **Test:** `tests/test_macos_install.py::test_native_engine_matrix_covers_every_metal_skill`, `tests/test_native_engines.py::test_the_native_engine_matrix_is_every_metal_skill`

### Requirement: bash 5 is the macOS recipe shell (Makefile init)
On macOS the Makefile MUST ensure bash 5 is the recipe shell: if the current recipe shell is not
bash 5 (`BASH_VERSION < 5`), must install bash via `brew install bash` (at init) if missing, set
that bash 5 as `SHELL`, and fail fast on a gate proving `BASH_VERSION >= 5`. No stage may run
under macOS system bash 3.2. On Linux (bash 5 already in /bin/bash) the gate MUST pass without
installing.

WHEN make initializes on macOS
THEN the recipe shell is bash 5, installed via brew if absent, proven by `BASH_VERSION >= 5`.

#### Scenario: bash 5 present
Given  a macOS host whose first bash on PATH is bash 5,
When   make initializes and the gate runs,
Then   the gate passes with no brew install.
- **Test:** `tests/test_macos_install.py::test_macos_make_uses_bash5`

#### Scenario: bash 5 missing (macOS)
Given  a macOS host whose recipe shell is not bash 5 and bash not yet installed via brew,
When   make initializes (`SHELL := $(shell python3 scripts/check_bash.py --resolve)`),
Then   it installs bash via `brew install bash` and sets it as SHELL before any recipe runs,
And    the same make run continues under bash 5 (no re-run needed).
- **Test:** `tests/test_macos_install.py::test_macos_make_installs_bash5_when_missing`

#### Scenario: bash version gate fails closed
Given  a shell whose `BASH_VERSION` is `3.2.x`,
When   the init gate evaluates,
Then   it fails loudly and no stage runs.
- **Test:** `tests/test_macos_install.py::test_bash5_gate_fails_closed_on_bash32`

### Requirement: the test image is Python 3.11
The `llgenie/test` image MUST use `python:3.11-slim` (bumped from 3.10) with lockfiles
recompiled, and the host gguf venv MUST be created with Python 3.11 (`scripts/check_python.py`;
brew installs python@3.11 on macOS when missing), so the same Python scripts run on Python
3.11 on the host and in CI.

WHEN the test image or the gguf venv is built
THEN it runs Python 3.11.

#### Scenario: the images and the venv are pinned to 3.11
Given  containers/test/Dockerfile, tools/Dockerfile and the tools create-venv recipe,
When   their base image and venv interpreter are read,
Then   both images are `python:3.11-slim`,
And    a venv that is not 3.11 is recreated with the python3.11 check_python resolves.
- **Test:** `tests/test_macos_install.py::test_test_image_and_tools_image_are_python311`, `tests/test_macos_install.py::test_venv_is_created_with_python311`

#### Scenario: test image base is 3.11
Given  containers/test/Dockerfile and tools/requirements*.lock compiled from the 3.11 base,
When   the test image is built,
Then   `python --version` inside it is Python 3.11.x.
- **Test:** CI job `ci-images` -> `make publish-ci-images` (image content asserted by the hash lock)

### Requirement: macOS runs every make test stage in the Python 3.11 venv, not a container
On macOS every `make` test stage (`ci-unit`, `ci-lint`, `ci-dispatch-e2e`, `ci-install`,
`ci-cpu-health`, `ci-top-tier`, `ci-engines`) MUST run its Python script natively with the
3.11 gguf venv (`~/llama-gguf-tools/.venv`), never inside the `llgenie/test` container; on
Linux the same targets MUST run in `llgenie/test` (`python:3.11-slim`). `make test-env` MUST prepare
that environment (Linux: pull the test image; macOS: `make -C tools venv-dev-install`, then install
`uv` with Homebrew when it is not already on PATH). `make install` on macOS installs Metal engines
as `uv` tools (LiteRT, MLX, TensorFold); a missing `uv` is a loud failure of that install, so the
environment step MUST provide it before `make install` runs. Every CI job MUST call `make test-env`
instead of `make test-image-pull`.

WHEN a test stage runs on macOS
THEN it runs with the 3.11 venv's python and no `docker run` of the test image.

#### Scenario: make ci-unit on macOS uses the venv
Given  the Makefile on a Darwin host,
When   `make -n ci-unit` is expanded,
Then   `test-unit` runs `python -m pytest` with `~/llama-gguf-tools/.venv/bin` first on PATH,
And    no `docker run ... llgenie/test` appears, while Linux keeps the 3.11 test image.
- **Test:** `tests/test_macos_install.py::test_macos_make_test_stages_run_in_the_311_venv_not_a_container`

#### Scenario: macOS test-env installs uv before make install
Given  a Darwin host whose PATH has no `uv`,
When   `make test-env` runs,
Then   it builds the Python 3.11 venv and installs `uv` with Homebrew,
And    `make install` can then install LiteRT, MLX and TensorFold as uv tools,
And    a still-missing `uv` fails that install loudly instead of being skipped.
- **Test:** `tests/test_macos_install.py::test_macos_test_env_installs_uv_before_make_install`

#### Scenario: macOS CI runs the Python 3.11 venv, not a Docker GitHub Action
Given  pipeline.yml, published.yml, the Docker action and the Makefile,
When   a macOS pipeline job starts,
Then   no workflow step runs `docker/setup-docker-action` or `colima start`,
And    every Docker-action step in pipeline.yml is gated with `runner.os == 'Linux'`, so macOS `make install`, health and top-tier never start Colima, and published.yml runs on Linux only,
And    openspec calls it only when `runner.os == 'Linux'` (macOS installs the pinned openspec CLI),
And    no workflow step runs `docker/setup-docker-action`,
And    `ci-install` prepares the environment (`make test-env`), then runs `make install`, `$HOME/bin/llgenie --dry` and `make uninstall` as separate make targets; macOS never runs those in a container; Linux runs `make install`, the dry run and `make uninstall` inside the test container,
And    every macOS job and every Linux job has `continue-on-error: false`, so both must succeed for the run to be green.
- **Test:** `tests/test_macos_install.py::test_macos_ci_does_not_run_docker_github_actions`

#### Scenario: a script the runner launches sees the venv
Given  the macOS CI runner, where `/bin/bash` is bash 3.2 invoked as a login shell,
When   the engine runner launches a server,
Then   it runs under the bash the Makefile selected (`LLGENIE_BASH`), which keeps the 3.11 venv on PATH,
And    it does not call bare `bash` (that is `/bin/bash` on the runner, and the server never binds).
- **Test:** `tests/test_macos_install.py::test_runner_serves_with_the_bash_make_selected_not_bin_bash`

#### Scenario: the loopback fixture listens without a hostname lookup
Given  the macOS 15 GitHub runner, where `socket.getfqdn()` stalls ~35s between bind and listen,
When   a test serves a frozen plan through the engine runner,
Then   the fixture is `scripts/loopback_server.py`, which binds and listens with no name lookup,
And    it is not `python3 -m http.server` (that lookup holds the socket CLOSED, so a 30s probe reports it dead).
- **Test:** `tests/test_macos_install.py::test_loopback_fixture_does_no_hostname_lookup`

### Requirement: a pull of a tag published by the same run is retried
`pull_published` MUST retry a registry pull that fails, because a push run publishes the pinned
tag from a parallel `engine-image` job that can still be pushing when `linux / install` starts.
After the retries it MUST still fail with `not published` so a tag that is never published does
not pass.

WHEN a pinned tag is not on the registry yet
THEN the pull is retried and succeeds once the tag is published.

#### Scenario: a tag that appears on the third pull is used
Given  a registry pull that fails twice and then succeeds, with matching digests,
When   pull_published runs,
Then   the tag is returned and the pull was tried three times.
- **Test:** `tests/test_macos_install.py::test_pull_published_retries_a_tag_the_parallel_job_has_not_pushed_yet`

### Requirement: the README link check survives a GitHub gateway timeout
`make check-registry` (`scripts/sync_registry.py check_links`) MUST retry a link that answers a
server error (5xx) or a network error, up to 5 times with backoff, and MUST report a 4xx at once.
It checks with GET (status only), not HEAD: from GitHub Actions runners github.com answers HEAD with 504s.

WHEN a README link answers 504 under load
THEN it is retried and only a link still failing after the retries is reported dead.

#### Scenario: a 504 is retried, a 404 is not
Given  one link that answers 504 twice then 200, and one that answers 404,
When   the links are checked,
Then   only the 404 is dead, after one request, and the slow link was requested three times.
- **Test:** `tests/test_trend_pick.py::test_link_check_retries_a_gateway_timeout_but_not_a_404`

### Requirement: a native version check does not need the engine's daemon
A native engine's detect command MUST count as installed when it prints a version line, even if it then exits non-zero because a daemon it talks to is not running. `ollama --version` on a fresh macOS install prints `ollama version is X.Y.Z` and exits 1 with `Warning: could not connect to a running Ollama instance`. That is the installed version, not a missing install. A non-zero exit with no version line MUST still be missing.

WHEN `ollama --version` prints a version and exits 1 because no daemon is running
THEN the engine is installed at that version.

#### Scenario: ollama's daemon warning is not a missing install
Given an ollama detect command that prints `ollama version is 0.35.1` and exits 1 with a connection warning,
When detect and native_status read it,
Then the engine is current at 0.35.1,
And    a non-zero exit with no version line is still missing.
- **Test:** `tests/test_engine_skills.py::test_detect_accepts_a_version_when_the_daemon_is_down`

### Requirement: macOS never starts an engine image
On macOS, `llgenie` and `make install` MUST NOT start or pull an engine image. An
Apple-Silicon Mac uses Metal and MUST run natively: the engines it offers are the
native Metal engines, and a container-only engine MUST NOT be offered or pulled.
An Intel Mac (`x86_64`, the `macos-15-intel` CI runner) has no native Metal engines
and MUST NOT install them and MUST NOT pull a cpu image. Linux MUST still pull this
host's container images, including the cpu fallback.

WHEN llgenie or make install runs on macOS
THEN no engine image is started or pulled, and only native Metal engines are offered.

#### Scenario: a metal host offers only native Metal engines
Given  a metal host,
When   its engines are listed,
Then   every offered engine has variant `metal`,
And    a container-only engine (vLLM) is absent,
And    a cuda/rocm-only engine (Strata, SGLang) is absent.
- **Test:** `tests/test_mac_trend_pick.py::test_metal_host_offers_only_native_metal_engines`

#### Scenario: macOS install does not pull an image
Given  an Apple-Silicon Darwin host and a container runtime that answers,
When   `make install` runs with no `--arch`, or with `--arch cpu`,
Then   it does not call the runtime and does not pull an image,
And    `--arch cpu` is refused,
And    Linux with the same call still pulls this host's images.
- **Test:** `tests/test_macos_install.py::test_macos_install_never_pulls_an_engine_image`

#### Scenario: an Intel Mac does not install Metal engines
Given  a Darwin host whose machine is `x86_64` (the macos-15-intel runner),
When   `make install` runs (no `--ensure`, no `--arch`),
Then   it installs no Metal engine and pulls no image,
And    it exits 0, because LiteRT, MLX and TensorFold publish arm64 wheels only,
And    its `test-built-engine` and `uninstall` are a no-op that exits 0,
And    an explicit non-metal `--arch` (e.g. `--arch cpu`, the health/top-tier assert) is REFUSED,
And    an explicit `--ensure <engine> --arch metal` (the llgenie pick, driven hermetically by
       `LLAMA_BACKEND=metal`) still runs the engine's native Metal install.
- **Test:** `tests/test_macos_install.py::test_intel_mac_install_does_not_install_metal_engines`, `tests/test_macos_install.py::test_intel_mac_built_engine_test_and_uninstall_are_noops`, `tests/test_macos_install.py::test_intel_mac_ensure_still_installs_a_metal_engine_natively`
