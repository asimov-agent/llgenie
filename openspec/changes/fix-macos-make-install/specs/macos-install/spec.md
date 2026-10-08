## ADDED Requirements

### Requirement: the --version check finds the engine version on any output line
`make test-built-engine` MUST pass a start script that exits 0 and prints an engine version on
any line of stdout or stderr that is not a container-runtime line, and MUST report that version
line. It MUST fail a script that exits non-zero or prints no version outside runtime lines.

WHEN a start script's `--version` output carries runtime warnings before or after the engine's
version line
THEN the check passes and reports the engine's version line.

#### Scenario: every --version output shape the runtimes print
Given  a start script's exit code and output in one of the shapes seen on Linux docker, docker on
       an arm64 Mac, nerdctl under Colima, an engine logging to stderr, CRLF output, runtime noise
       only, a SIGILL crash, a version with a non-zero exit, and no output,
When   the --version check reads it,
Then   it passes exactly when the engine printed a version and exited 0,
And    it reports the engine's version line, never the runtime's warning.
- **Test:** `tests/test_macos_install.py::test_version_check_accepts_the_version_line_anywhere`

#### Scenario: a runtime warning after the version line
Given  four installed start scripts that print the engine version and then a runtime warning,
When   `make test-built-engine` runs them,
Then   all four pass.
- **Test:** `tests/test_macos_install.py::test_built_engine_test_passes_when_a_runtime_warning_follows_the_version`

#### Scenario: a crashed engine still fails
Given  a start script whose engine dies with SIGILL and exits 1,
When   `make test-built-engine` runs it,
Then   the check fails.
- **Test:** `tests/test_macos_install.py::test_built_engine_test_still_fails_a_crashed_engine`

### Requirement: the container runtime is docker
The Makefile's `RUNTIME` and `engine_image.RUNTIME` MUST be `docker` on Linux and macOS
(Colima's docker runtime); nerdctl MUST NOT be used. An explicit `RUNTIME` MUST be kept.

WHEN make or the python scripts resolve the container runtime
THEN it is docker unless RUNTIME is set.

#### Scenario: docker by default
Given  no RUNTIME in the environment,
When   engine_image is imported and make resolves RUNTIME,
Then   both are docker, and the Makefile's runtime block never names nerdctl.
- **Test:** `tests/test_macos_install.py::test_runtime_is_docker_in_python_and_make`

#### Scenario: an explicit RUNTIME
Given  RUNTIME pointing at another docker CLI,
When   engine_image is imported and make resolves RUNTIME,
Then   both keep it.
- **Test:** `tests/test_macos_install.py::test_explicit_runtime_is_kept`

### Requirement: a dead runtime is not reported as an unpublished image
`make install` MUST report a failed pull as `container runtime '<rt>' does not answer` when the
runtime's engine does not answer, and as `not published in <registry>` only when it does.

WHEN the pull fails and `<runtime> info` fails
THEN install names the runtime, not the registry.

#### Scenario: the runtime does not answer
Given  a runtime whose engine does not answer, so every pull fails,
When   make install pulls the core engines,
Then   it fails and names the runtime, and never says "not published".
- **Test:** `tests/test_macos_install.py::test_install_reports_a_dead_runtime_not_an_unpublished_image`

#### Scenario: the runtime answers and the tag is missing
Given  a working runtime and a tag that is not on the registry,
When   make install pulls the core engines,
Then   it fails with "not published".
- **Test:** `tests/test_macos_install.py::test_install_still_reports_an_unpublished_image_when_the_runtime_answers`

### Requirement: start scripts run the image as the platform it was built for
Every start script and shim MUST pass `--platform <os>/<arch>[/<variant>]` of the pulled image to
`<runtime> run`, read from the image, and MUST pass none when the platform cannot be read.

WHEN make install writes a start script for a pulled image
THEN every `run` in it carries that image's platform.

#### Scenario: amd64 and arm64 images
Given  pulled images whose platform is linux/amd64 (or linux/arm64/v8),
When   make install writes the start scripts,
Then   every run line in every script and shim carries `--platform <that platform>`.
- **Test:** `tests/test_macos_install.py::test_start_scripts_pin_the_pulled_images_platform`

#### Scenario: platform unknown
Given  images whose platform cannot be read,
When   make install writes the start scripts,
Then   no script passes --platform.
- **Test:** `tests/test_macos_install.py::test_no_platform_flag_when_the_image_platform_is_unknown`

#### Scenario: reading the image platform
Given  a runtime whose `image inspect` prints os/arch[/variant], fails, or prints an unfilled template,
When   the image's platform is read,
Then   it is the os/arch[/variant], or "" when unreadable.
- **Test:** `tests/test_macos_install.py::test_image_platform_reads_os_arch_variant`

### Requirement: the same CI pipeline on Linux and macOS
CI MUST run one pipeline twice in parallel, on a Linux and on a macOS runner, with the same
jobs, `make` commands and asserts. The only per-OS step MUST be the Docker setup (macOS:
Docker's own `docker/setup-docker-action`, plus `docker/setup-buildx-action`). The published-image install (`make test-install-published`
per backend) MUST run on both. Only the linux jobs MAY fail the run: every macOS job MUST be
`continue-on-error` (input `optional: true`), so it reports but never blocks the PR. No
macOS-only make target or CI job may exist.

WHEN a CI run starts
THEN the linux and the macos pipeline run the same jobs through the same make commands.

#### Scenario: linux and macos call the same pipeline
Given  ci.yml, pipeline.yml, published.yml, the Docker action and the Makefile,
When   the callers of each shared pipeline are read,
Then   a push starts one run (trigger `push` on every branch, no `pull_request` trigger),
And    linux and macos call pipeline.yml on ubuntu-latest and macos-15-intel,
And    linux-published and macos-published call published.yml on the same runners,
And    every pipeline job runs on the caller's runner, install through `make test-install-ci`,
And    every macOS job is `continue-on-error` (optional) and no linux job is,
And    the only OS-specific steps are `docker/setup-docker-action` + `docker/setup-buildx-action`
       on macOS (no Colima), with the checkout mounted writable,
And    `make test-install-ci` installs, tests, says hi, picks a trend model, uninstalls and runs
       `make test-uninstalled`,
And    no macOS-only make target or job exists.
- **Test:** `tests/test_macos_install.py::test_linux_and_macos_run_the_same_pipeline`

#### Scenario: the real install and uninstall on both
Given  a Linux runner with docker and a macOS runner with Docker from docker/setup-docker-action,
When   the install job runs `make test-install-ci`,
Then   make install reports every engine OK, llgenie answers "hi", the trend pick answers
       "hi", and make uninstall leaves no installed file and no container, on both.
- **Test:** CI jobs `linux / install` and `macos / install` -> `make test-install-ci`

### Requirement: test-agents-read provisions its own Python 3.12 venv
`make test-agents-read` MUST build its Python 3.12 venv (hermes-agent==0.19.0 + pytest)
through make (`agents-read-venv`), then scan AGENTS.md and run `tests/test_agents_read.py`
in it. The CI job MUST only provide python3.12 and call `make test-agents-read`, never pip
or pytest directly.

WHEN `make test-agents-read` runs on a host with python3.12
THEN make builds the venv if missing and the guard plus its tests run in it.

#### Scenario: the venv is built by make and CI only calls make
Given  the Makefile and pipeline.yml,
When   the test-agents-read recipe and the agents-read job are read,
Then   test-agents-read depends on agents-read-venv, which creates a venv with python3.12
       and installs the pinned hermes-agent and pytest, outside the repo,
And    the scan and `tests/test_agents_read.py` run with that venv's python,
And    the agents-read job runs no pip or pytest itself, only `make test-agents-read`.
- **Test:** `tests/test_macos_install.py::test_agents_read_builds_its_own_python312_venv`

#### Scenario: a fresh host gets the venv and the guard runs
Given  a host with python3.12 and no agents-read venv,
When   `make test-agents-read` runs,
Then   the venv is built, AGENTS.md scans clean, and the guard's tests pass.
- **Test:** CI jobs `linux / agents-read` and `macos / agents-read` -> `make test-agents-read`

### Requirement: macOS repairs a broken Colima before a container starts
On macOS, make install (before any pull) and llgenie (before an engine container starts)
MUST check that the container runtime answers and that the Colima VM resolves the registry.
A stopped VM MUST be started with explicit DNS resolvers; a running VM that cannot resolve
the registry MUST get those resolvers written into it, and MUST be restarted with them only
when that does not help. A healthy VM, and any non-macOS host, MUST never be touched.

WHEN Docker through Colima is stopped or its DNS does not answer
THEN make install and llgenie repair it before pulling or starting a container.

#### Scenario: healthy, DNS broken, DNS still broken, stopped
Given  a Mac whose Colima VM is healthy, has DNS that a resolver rewrite fixes, has DNS that
       only a restart fixes, or is stopped,
When   the container environment is checked,
Then   it works afterwards,
And    Colima was repaired only as far as needed, always with `--dns 1.1.1.1 --dns 8.8.8.8`.
- **Test:** `tests/test_macos_install.py::test_macos_colima_is_repaired_before_a_container_starts`

#### Scenario: Linux is never touched
Given  a Linux host with docker down and a colima binary on PATH,
When   the container environment is checked,
Then   it reports OK without calling colima.
- **Test:** `tests/test_macos_install.py::test_linux_container_env_is_never_touched`

#### Scenario: make install and llgenie check first
Given  the install script and the llgenie launcher,
When   their start paths are read,
Then   each calls the check before pulling or running a container.
- **Test:** `tests/test_macos_install.py::test_install_and_llgenie_check_the_container_env_first`
