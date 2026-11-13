# Proposal: agent-image-base-pinned

## Why

`containers/agent/Dockerfile` declares `ARG TEST_IMAGE=llgenie/test:latest` and builds `FROM ${TEST_IMAGE}`. Trivy flags the default as a dockerfile misconfig (`':latest' tag used`) — measured 2026-11-13 on `main` `da2fc5adb`: it is the ONLY misconfig row left in the whole tree (0 vulns, 0 secrets, 1 misconfig). Every wired build path (`scripts/ci_images.py` `ensure`/`_build_local`/`_buildx_push`, all `make agent-image*` targets, all CI legs) already passes the exact hashed ref via `build_args` — the default is reachable only from an ad-hoc `docker build`, where it silently bakes a moving base into the image every bot lane runs in.

Issue: #2617.

## What Changes

- `containers/agent/Dockerfile`: `ARG TEST_IMAGE=llgenie/test:latest` → `ARG TEST_IMAGE` (no default). `FROM ${TEST_IMAGE}` then fails loudly (empty base name) without the build-arg instead of resolving to the mutable alias.
- `tests/test_ci_images.py`: new lock `test_agent_dockerfile_has_no_latest_base_default` — the ARG line carries no default and the pre-FROM block names no `:latest` base.
- No behavior change to any wired path: `build_args` already always injects the hashed `--build-arg` (existing lock `test_publish_agent_pins_the_test_image_it_builds_from` unchanged).

## Impact

- Affected specs: `ci-images` (agent image base pinning)
- Affected code: `containers/agent/Dockerfile`, `tests/test_ci_images.py`
- Follow-on: trivy dockerfile misconfig count drops 1 → 0 across the tree; the daily security verdict gate sees no dockerfile findings.
