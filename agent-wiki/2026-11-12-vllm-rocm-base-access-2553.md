# 2026-11-12 — vllm-rocm-base-access (#2553 / PR pending)

## What was verified

- Root cause measured live: engine-build run 43221661126 (fleet #664, job
  engine-build-vllm-rocm, detect stage) — `/opt/python/bin/vllm` exits 126 and
  `from vllm import __version__` raises ModuleNotFoundError as uid 1000. The base image
  `rocm/vllm:rocm10.1.0_ubuntu24.04_py3.14-pytorch_2.13.0_vllm-0.29.0` hosts vllm in a
  root-built uv venv at `/opt/python` (manifest sha256:e0ea9a10b729573e…, config
  sha256:2d41964ed4f4c773…, `UV_PYTHON=/opt/python/bin/python`).
- Fix shape: `base_access` key in the engine skill (vllm `container.rocm:
  ["/opt/python"]`), `render_variant` attaches it ONLY to the declaring variant,
  `_base_access_run` renders a directory-only `find -type d -exec chmod a+rx` between the
  service-user RUN and `USER 1000:1000`.
- Tag-identity proof measured on the branch: cuda `4c1f3eee` and cpu `524f7326` digests
  byte-identical before/after; rocm moves `db98981b` → `ba13b1d7` (the new image must not
  reuse the broken tag identity).
- `make generate-engine-params` rc=0, generated diff touches exactly
  `containers/engines/dockerfiles/vllm/Dockerfile.rocm` + `containers/engines/params/vllm.json`.
- Targeted hermetic run: 136/136 (test_engine_skills + test_engine_image_matrix) incl. the
  new lock `test_vllm_rocm_opens_its_root_only_base_venv_for_uid_1000`.
- Lane-lag fix proven in the same branch: `test_an_engine_with_no_base_copy_is_deferred`
  hard-coded `== {brand-new-engine}` while the #2559 union rule correctly defers a branch's
  own retagged engines; the assertion now composes `{synthetic} ∪ retagged_engine_ids(base)`
  (measured `{"brand-new-engine", "vllm"}` here) — any params-retag PR since #2560 would have
  reddened it.
- `make openspec-validate NAME=vllm-rocm-base-access` rc=0.

## Current status

Issue #2553 body restated into the six-section shape (liveness marker line kept first so
the bot's idempotence still finds it; both tag identities named). Full `make test-unit`
re-run in progress on the committed branch. After merge, registry-liveness' push trigger
dispatches the `vllm`/`rocm` `push=true` publish of `3a4d82f5-ba13b1d7-rocm` from main.
