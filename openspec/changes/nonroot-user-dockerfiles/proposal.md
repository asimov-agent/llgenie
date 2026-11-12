# Proposal — nonroot-user-dockerfiles (#2504)

## Why

`trivy-misconfig` reports rule `DS-0002` ("Specify at least 1 USER command in Dockerfile with non-root user as argument") against all 37 shipped Dockerfiles on `main`: every engine image this repository builds serves as root. The lane filed one issue per file (#2397-#2428, #2463-#2467); the umbrella #2504 consolidates the family into one objective with one implementing PR.

## What Changes

One generator-side fix pass, so every shipped Dockerfile declares a non-root service user without changing what the images build:

1. `scripts/engine_skills.py` gains shared user-creation constants: an idempotent `RUN` (`getent` guards, so upstream bases that already own uid/gid 1000 - nvcr.io, lmsysorg/sglang, vllm - are never double-created) that creates `llgenie` uid/gid 1000 with HOME `/var/lib/llgenie`.
2. `render_base_dockerfile` appends the create-`RUN` plus `USER 1000:1000` to each shared base (`base/Dockerfile.cpu|cuda|rocm|vulkan`).
3. `render_dockerfile` appends the engine variant of the create-`RUN` (also chowns `/models`, `/models/hf`, `/opt/llgenie/app`) plus `USER 1000:1000` before the `HEALTHCHECK`, and emits `USER root` after every `FROM` in a derived image so build-stage installs stay privileged; only the served process is unprivileged.
4. `containers/test/Dockerfile` is NOT touched by this change: it is a hash input of the published `llgenie/test` CI image, and editing it in a fork-head PR moves a GHCR tag no PR token may publish (issue #155) — every `test-env`-consuming CI job of that PR then fails at `docker pull` (measured on PR #2517 head `09f814f79`: SKIP-publish `test:8fb483ae90f5`, then `linux/lint|unit|install|cpu-health` red). Its non-root fold and the scope lane that unpublishes this deadlock are filed as their own issue, #2518.
5. `make generate-engine-params` re-renders all 36 generated Dockerfiles; the new base content shifts the base tags, and the derived `FROM` lines follow automatically (the parity gate `make check-engine-params` proves tree == render).

## Impact

- Affected specs: engine image build (image inputs shift: every image tag recomputes from the new Dockerfile bytes; CI's test-image jobs rebuild the changed cells and post-merge `main` republishes the pins - the same dependency chain as any engine bump, issue #186).
- Affected code: `scripts/engine_skills.py`, `containers/engines/base/Dockerfile.*` (4), `containers/engines/dockerfiles/**` (32). `containers/test/Dockerfile` is deferred to #2518 (its published tag gates PR CI).
- No behavior change to builds: root is re-enabled after each `FROM`; test stages already run `-u root` via `TEST_OPTS`/`ENGINE_TEST_ARGS`.
