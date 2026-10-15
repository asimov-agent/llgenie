# 2026-10-12 — bump PR publish order (issue #169, OpenSpec fix-bump-pr-install-pull-order)

## What was verified against the spec

- **A same-repo `pull_request` run does publish its engine images.** `make push-engine`
  is an unconditional step of every `engine-image-*` job. Run 38121659510 job
  `engine-image-llama.cpp-cuda` logged `pushed ghcr.io/asimov-agent/llgenie/llama-cpp:23b0202a-021e11d2-cuda`,
  and the current bump tags answer `200` on the GHCR manifest endpoint
  (`llama-cpp:f2cc7282-3673c4ad-cpu`, `:f2cc7282-d80c87af-cuda`,
  `llama-cpp-prism:e8fd209c-cb5b6dc0-cpu`). The old AGENTS.md line "pull_request runs
  (read-only token) never push" was wrong and is corrected.
- **The defect is ordering, not publishing.** `pipeline.yml`'s `install` job needs only
  `ci-images`, so it pulls while `engine-image-*` is still building. Run 38112341463
  (PR #130): `[install] FAIL llama.cpp/cpu: not published in ghcr.io/asimov-agent` at
  04:48:08 vs `engine-image-llama.cpp-cpu` finishing at 04:51:26. Run 38186233274
  (PR #168, engine-bump run 38186202923): `linux / install` failed 23:59:17 → 00:00:41,
  the cpu image pushed at 00:05:28.
- **Why only some paths raced:** `install` pulls through
  `install_engine_launchers.ensure_image` → `engine_image._available` (one pull attempt),
  while `engine_image.pull_published` (the `test-published-engine` path) already retried
  the publish race. The gate closes the install path without changing local build behaviour.

## Key decisions

- Gate, not a retry inside `_available`: a retry there would stall every local
  `make build-engine` on an unpublished base image. `make ci-wait-engine-images` is a CI
  ordering gate that does a manifest lookup per tag — no pull, no build, no fallback.
- `install_engine_launchers.install_plan()` is now the ONE place the "images install
  pulls" list is built; `install()` and `wait_published()` both read it, so the gate can
  never wait for a tag install would not pull (locked by a test).
- macOS install is not gated (it never pulls a container image, issue #120).
- Issue #155 stays open for the fork-PR read-only-token case; its body was corrected to
  match the measured behaviour and cross-links #169.

## Current status

- Branch `feat/publish-bump-pr-images`, PR #170 to `asimov-agent/llgenie:main`, review
  requested from `asimov-agent` (read back as `reviewRequests=['asimov-agent']`).
- `make lint` and `make openspec-validate NAME=fix-bump-pr-install-pull-order` green on
  the branch; `make ci-wait-engine-images ARCH=cpu` returns 0 against the real registry.
- `tests/test_ci_publish_order.py` is wired into `make test-unit`; the suite runs in the
  PR's CI `unit` job (not on the host).

## Follow-up: the gate's own wiring (commits `1a33907`, then the unit fixes)

CI on the first head (`784382c`, run 38187824799) proved the gate works — `linux / install`
went green — but failed the PR's own wiring:

```
FAILED tests/test_ci_images.py::test_macos_runs_the_linux_pipeline_file_job_for_job
FAILED tests/test_ci_images.py::test_every_pipeline_job_runs_one_ci_make_target
```

`install` had two `make ci-*` steps (`ci-wait-engine-images` beside `ci-install`), and the
contract is exactly one `make ci-<job>` target per pipeline job. The gate moved into the
`ci-install` recipe (`1a33907`) and the workflow step was deleted.

The second head (`ef32a5b`, run 38191035512, job 114623769153) then failed `make ci-unit` on
three asserts, all of them about the wiring rather than the gate:

```
FAILED tests/test_macos_install.py::test_macos_ci_does_not_run_docker_github_actions
    assert same in recipe and "Darwin" not in recipe  -> AssertionError: ci-install
FAILED tests/test_ci_publish_order.py::test_the_install_job_runs_one_make_target
    AssertionError: ['make ci-free-disk', 'make ci-install', 'make test-clean']
FAILED tests/test_ci_publish_order.py::test_macos_install_is_not_gated - IndexError
```

Root causes and fixes:

- `ci-install` must stay **OS-neutral** (`test_macos_install.py:897` asserts `"Darwin" not in
  recipe` for `ci-install`, `ci-cpu-health` and `ci-top-tier`): the OS decision belongs in the
  sub-target. The `ifeq ($(HOST_OS),Darwin)` branch therefore moved into
  `ci-wait-engine-images` itself — Darwin prints that it pulls no engine image, Linux does the
  manifest lookups.
- The one-target test must read the ci targets the way `test_ci_images._make_targets` does
  (`make (ci-[a-z0-9-]+)`, `ci-free-disk` excluded); matching every `make ` step counted the
  disk helper and the cleanup helper.
- The macOS test now asserts the contract directly: no `Darwin` in `ci-install`, the OS branch
  and the `--wait-published` lookup only in the gate target.

The spec gained the scenario *the gate is a prerequisite, not a second job step* with both
test references, and its macOS scenario now names `test_macos_install.py` as the lock.

## Third CI round (head `c942e6c`, run 38192010026, jobs 114626690070 / 114626690017)

`linux / unit` and `macos / unit` failed at `make ci-unit`:

```
FAILED tests/test_macos_install.py::test_macos_make_test_stages_run_in_the_311_venv_not_a_container
    assert '$(VENV)/bin' in '\t@echo "ci-wait-engine-images: macOS pulls no engine image…"'
FAILED tests/test_ci_publish_order.py::test_macos_install_is_not_gated
    ValueError: not enough values to unpack (expected 3, got 2)
```

Two causes, one of them a real Makefile defect the test happened to expose:

- **`ci-wait-engine-images` was defined at Makefile:218, before `HOST_OS := $(shell uname -s)`
  at 428.** make evaluates `ifeq` while it *parses* the file, so at line 218 `$(HOST_OS)` is
  empty and the Linux branch is taken on macOS too — the gate would have polled the registry
  on a Mac. `make -n … HOST_OS=Darwin` cannot show this: a command-line variable overrides the
  `:=` for the whole parse. The target moved below the `HOST_OS` assignment, next to
  `ci-install`, and the ordering is now asserted.
- `test_macos_make_test_stages_run_in_the_311_venv_not_a_container` read the **first**
  `ifeq ($(HOST_OS),Darwin)` block in the file and asserted it is the test runner. Any target
  may branch on the OS, so the block is now selected by content (`TEST_RUN :=` in it) rather
  than by position.
- `test_macos_install_is_not_gated` unpacked `gate.split("else", 1)` into three names; the
  recipe splits on `"\nelse\n"` into two.

`make -n ci-install` still runs `test-env` -> the gate (`--wait-published --arch cpu`) ->
`ci-install-run`; the gate's Darwin branch echoes and does no lookup.

## The four bump PRs (run 38186202923) — what is actually red

| PR | Engine | Red job | Cause |
|---|---|---|---|
| #168 | llama.cpp | `linux / install` | the publish race this change fixes (#169) |
| #165 | tensorfold | `engine-image-tensorfold-cuda` | the bump pip-installs `v1.0.7`, which upstream 1.0+ refuses (issue #171, PR #173) |
| #165 #166 #167 #168 | all | `linux / unit` | `test_changed_engines_scopes_matrix` compares the branch with `origin/main` and expects the `engine: none` placeholder; a pin move is a diff (fixed by PR #173) |

Each PR carries a comment naming its blocker and its re-run condition. #172 was closed as a
duplicate of #171. Nothing here is merged: the agent waits for a reviewer approval.

