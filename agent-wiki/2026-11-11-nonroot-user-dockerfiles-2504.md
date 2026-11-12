# 2026-11-11 — Non-root USER in every shipped Dockerfile (#2504)

Implements issue #2504 (umbrella for the 37 per-file `trivy-misconfig` `DS-0002`
issues #2397-#2428, #2463-#2467, all closed `duplicate` of the umbrella).

## What was verified

- Generator change (`scripts/engine_skills.py`): one idempotent uid/gid 1000
  create `RUN` (getent guards - upstream bases nvcr.io / lmsysorg / vllm may
  already own 1000), appended with `USER 1000:1000` to the four shared bases and
  the 32 engine Dockerfiles (engine variant also chowns `/models`, `/models/hf`,
  `/opt/llgenie/app`). Derived images emit `USER root` after every `FROM`, so
  build-stage installs stay privileged; only the served process is uid 1000.
- `containers/test/Dockerfile`: same user + system `safe.directory` + trailing
  `USER 1000:1000`. The Makefile's `TEST_OPTS`/`ENGINE_TEST_ARGS` already run
  every stage with an explicit `-u root`, so stage behavior is unchanged; the
  trailing USER only removes the bare-root default a misconfig scan flags.
- Re-render via `make generate-engine-params`: 36 Dockerfiles updated; the base
  content shift moves the base tags (e.g. `llgenie/base-cpu` `d0eb107fa0` ->
  `646a2d1444`) and every derived `FROM` follows; `make check-engine-params`
  rc=0 ("0 file(s) stale") proves tree == render at the new head. `make lint`
  rc=0.
- Image identity consequence: Dockerfile bytes are part of the image tag input
  (`image_inputs`), so every engine image tag recomputes - the same dependency
  chain as an engine bump (issue #186): CI's test-image jobs rebuild the cells
  on the PR, and post-merge `main` republishes the pins. No local image builds
  (user directive 2026-11-11).

## Decisions

- One fix pass on the generator, never 37 hand edits: the Dockerfiles are
  GENERATED, so the USER lives in `render_base_dockerfile`/`render_dockerfile`
  and the parity gate keeps them honest.
- uid/gid 1000 was chosen deliberately: host-mounted model dirs and CI runner
  workspaces are owned by uid 1000, so the unprivileged serve writes where the
  mounts expect.
- HOME `/var/lib/llgenie` is created up front so any process that needs a HOME
  (ollama, HF cache fallbacks) has a writable one owned by 1000.

## Current status

OpenSpec change `nonroot-user-dockerfiles`; trivy head-scan + negative control
and the engine test gates recorded in `tasks.md`; full `make test-unit` and the
PR follow.
