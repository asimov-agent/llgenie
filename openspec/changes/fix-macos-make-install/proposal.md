# make install works on an Apple-Silicon Mac with Docker (Colima)

## Why

`make install` failed on an Apple-Silicon Mac (macOS, Colima) although every published image
was on GHCR and every engine ran (issue #112):

1. `scripts/engine_image.py` used `docker` whenever the docker CLI was on PATH. With Colima on
   the containerd runtime there is no docker socket, every pull failed, and install printed
   `FAIL llama.cpp/cpu: not published in ghcr.io/asimov-agent`. The Makefile preferred nerdctl;
   the python scripts did the opposite.
2. `make test-built-engine` read only the LAST output line of `<script> --version`. The runtime
   prints its own lines next to the engine's version: docker's
   `WARNING: The requested image's platform (linux/amd64) does not match the detected host platform (linux/arm64/v8) ...`,
   nerdctl's `time="..." level=warning msg="force cleanup timed out ..."`. All four scripts were
   reported FAIL (`0 ok, 4 failed`) while each printed `installed version: ...` and exited 0.
3. The start scripts ran the linux/amd64 images on an arm64 host with no `--platform`, so docker
   warned on every run.

CI never saw it: every install job runs on an amd64 Linux runner with docker.

## What Changes

- Runtime: docker only, on Linux and macOS (Colima's docker runtime), in the Makefile
  (`RUNTIME ?= docker`) and in `engine_image.RUNTIME`. `RUNTIME=` still overrides. No nerdctl.
- `make install`: a failed pull with a runtime that does not answer is reported as
  `container runtime '<rt>' does not answer`, never as "not published".
- `make test-built-engine`: passes on exit 0 with an engine version on ANY output line that is
  not runtime noise (`WARNING:` / `time="..." level=` lines); reports that version line.
- Start scripts and shims run the image with `--platform <os>/<arch>[/<variant>]` read from the
  pulled image (`engine_image.image_platform`), not hardcoded.
- macOS self-repair (`engine_image.ensure_container_env`), called by make install before any
  pull and by llgenie before an engine container starts: a stopped Colima VM is started with
  explicit DNS resolvers; a VM that cannot resolve `ghcr.io` gets the resolvers written into
  it, then a restart with them when still broken. No-op on Linux.
- The same make commands on Linux and macOS: plain `RUNTIME ?= docker` in the Makefile, the
  new test file in `make test-unit`, and `make test-install-ci` ends with `make test-uninstalled`
  (nothing installed left, a foreign file kept, no engine container); no macOS-only target. The macOS
  special case lives in the logic only (`--platform`, the version check, the Colima
  self-repair), never in a separate command.
- Merge gate (branch protection on `main`): every `linux / *` job and the four
  `linux-published / install-published-*` installs are required. Every macOS job (both macOS
  `make install` jobs included) runs on every push and reports, but does not block: `ci.yml` passes `optional: true` to the
  macOS callers, which makes every macOS job `continue-on-error`, so a macOS failure or
  timeout never turns the run red.
- One CI run per push: `ci.yml` triggers on `push` (every branch) only; the `pull_request`
  trigger is gone, so a push to a PR branch no longer runs everything twice.
- The same CI pipeline on both: `ci.yml` calls `pipeline.yml` twice in parallel, `linux`
  (ubuntu-latest) and `macos` (macos-15-intel, Docker from Docker's own `docker/setup-docker-action`: Docker CE in a
  Lima vz VM with the checkout mounted writable, plus `docker/setup-buildx-action`), with the same jobs,
  make commands and asserts. The only per-OS step is `.github/actions/docker`. The engine
  images are built once on Linux, then `published.yml` (`make test-install-published` per
  backend) installs them on both (`linux-published`, `macos-published`).
- Removed the macOS-native jobs `engine-smoke-mac` and `server-variants-mac`: a Mac now gets
  the same container images as Linux.
- `make test-agents-read` provisions itself: it builds a Python 3.12 venv
  (`~/.cache/llgenie/agents-read-venv`, outside the repo; hermes-agent==0.19.0 + pytest) and runs the AGENTS.md scan plus
  `tests/test_agents_read.py`, so it works on any host with python3.12. It used to fail on a
  dev host (Linux or macOS) without a pre-installed hermes-agent; CI only passed because the
  job ran pip and pytest itself. The CI job now only provides python3.12 and calls make.
- README: macOS prerequisites (Rosetta 2, Colima docker runtime) and the new targets.

## Impact

`Makefile`, `scripts/engine_image.py`, `scripts/install_engine_launchers.py`,
`.github/workflows/ci.yml`, `.github/workflows/pipeline.yml`, `.github/workflows/published.yml`,
`.github/actions/docker/action.yml`, `tests/test_macos_install.py`, `tests/test_ci_variant_matrix.py`,
`tests/test_engine_skills.py`, `README.md`.

Issue: #112.
