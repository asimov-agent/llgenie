## 1. Fix

- [x] 1.1 Runtime: docker only (`RUNTIME ?= docker` in the Makefile, `engine_image.RUNTIME`), no nerdctl; explicit `RUNTIME` kept.
- [x] 1.2 `make install`: a failed pull with a runtime that does not answer names the runtime, not "not published".
- [x] 1.3 `make test-built-engine`: `version_ok` passes on exit 0 with a version on any non-runtime-noise line and reports that line.
- [x] 1.4 Start scripts + shims: `--platform <os>/<arch>[/<variant>]` read from the pulled image (`engine_image.image_platform`).
- [x] 1.5 Makefile: plain `RUNTIME ?= docker`; `make test-install-ci` ends with `make test-uninstalled`; no macOS-only target.
- [x] 1.6 CI: `ci.yml` calls `pipeline.yml` as `linux` (ubuntu-latest) and `macos` (macos-15-intel) and `published.yml` as `linux-published` / `macos-published`; `engine-smoke-mac` and `server-variants-mac` removed.
- [x] 1.10 Branch protection on `main` requires every `linux / *` job and the four `linux-published` installs; every macOS job runs and reports but does not block.
- [x] 1.12 macOS jobs never fail the run: `optional` input on `pipeline.yml`/`published.yml` -> `continue-on-error` on every job, set only by the `macos`/`macos-published` callers; locked by `test_linux_and_macos_run_the_same_pipeline`.
- [x] 1.9 One CI run per push: `ci.yml` triggers on `push` only (no `pull_request` duplicate).
- [x] 1.8 macOS self-repair `ensure_container_env` (stopped VM / VM DNS), called by make install and llgenie; verified for real on the Mac (colima stop -> started; VM resolv.conf broken -> rewritten, pull OK).
- [x] 1.11 CI macOS Docker: `.github/actions/docker` uses `docker/setup-docker-action@v5` (vz, virtiofs, `--mount-writable`) + `docker/setup-buildx-action@v4` instead of Colima; locked by `test_linux_and_macos_run_the_same_pipeline`.
- [x] 1.13 `make test-agents-read` builds its own Python 3.12 venv (`agents-read-venv`: hermes-agent==0.19.0 + pytest), scans AGENTS.md and runs `tests/test_agents_read.py`; the CI job only provides python3.12 and calls make (no direct pip/pytest).
- [x] 1.7 README: macOS prerequisites, RUNTIME rule, the two pipelines.

## 2. Tests

- [x] 2.1 `tests/test_macos_install.py` in `make test-unit`: every --version output shape, docker runtime (python + make), dead-runtime message, `--platform` in every script, `image_platform` parsing, the same pipeline on Linux and macOS.
- [x] 2.2 Sabotage: with the old last-line check the Mac warning shapes fail; with the fix they pass.
- [x] 2.3 Local Mac host (Colima docker runtime, Rosetta): `make test-install-ci` exit 0 (install `4 ok, 0 failed`, install tests pass, "hi" answered, trend pick answered "hi", uninstall left nothing).
- [x] 2.4 `make lint`, `make test-unit` and `make openspec-validate NAME=fix-macos-make-install` pass.
- [x] 2.5 CI: the `linux` and `macos` pipelines run the same jobs and make commands (locked by `test_linux_and_macos_run_the_same_pipeline`); their run results are reported on PR #113, not in this checklist.
