# 2026-10-07 fix-macos-make-install (issue #112, PR #113)

## What failed on the Apple-Silicon Mac (Colima)

- Colima on the containerd runtime + Homebrew docker CLI: `engine_image.RUNTIME` was `docker`
  (CLI on PATH, no socket) -> every pull failed -> "not published in ghcr.io/asimov-agent".
- `test-built-engine` 0 ok / 4 failed: each script printed `installed version: ...` and
  exited 0, but the check read only the last line (a runtime warning on the Mac).
- Prism under qemu (Colima without Rosetta) crashed with SIGILL; with `--vz-rosetta` it runs.

## Fix

- Runtime: plain `docker` (Makefile + engine_image), no nerdctl; a dead runtime is named in the
  install error; version found on any non-runtime line; `--platform` from the pulled image.
- `make test-install-ci` ends with `make uninstall` + `make test-uninstalled`; no macOS-only
  make target.
- macOS self-repair `ensure_container_env` (stopped Colima VM / VM DNS), no-op on Linux.

## CI

- `ci.yml` (push on every branch only) calls `pipeline.yml` + `published.yml` as `linux`
  (ubuntu-latest) and `macos` (macos-15-intel): same jobs, same make commands.
- macOS Docker: Docker's own `docker/setup-docker-action@v5` (Lima vz VM, virtiofs,
  `--mount-writable`) + `docker/setup-buildx-action@v4`, replacing Colima in CI. First VM
  boot costs about 6 min per job.
- macOS never blocks: the macos callers pass `optional: true` -> `continue-on-error` on every
  macOS job. Branch protection on `main` requires only `linux / *` and the four
  `linux-published / install-published-*` jobs.

## Verified on the host (Colima docker runtime, vz + Rosetta)

- `make test-install-ci ARCH=cpu` exit 0: `test-built-engine` 4 ok, 0 failed; install tests
  7 passed; "hi" answered; trend pick (DeepSeek R1 1.5B) answered "hi"; uninstall left no
  installed file and no container, foreign file kept.
- `make lint`, `make test-unit` (646 passed), `make openspec-validate` / `openspec-tasks-check`,
  `test-health`, `test-agents-e2e` (2), `test-top-tier-ci` (15) / `-serve-ci` (1) /
  `-cli-ci` (2), `cron-snapshot`, `watch-report`, skills/registry/params checks: all pass.
- `make test-agents-read` failed on any host without a pre-installed hermes-agent (not a
  macOS bug: CI ran pip itself). Now make builds the Python 3.12 venv
  (`~/.cache/llgenie/agents-read-venv`); from a fresh build: AGENTS.md clean, 13 passed; the
  second run reuses the venv. The venv sits outside the repo because the guard's test rejects
  a hermes module imported from the repo.
- CI run 37709980122: all 10 `linux / *` jobs green.

## Open

- PR #113 waits for a reviewer approval; macOS CI results are informational.
