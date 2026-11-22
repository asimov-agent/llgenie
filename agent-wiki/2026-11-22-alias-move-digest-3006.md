# Byte-preserving alias move for the registry-liveness heal (issue #3006)

Date: 2026-11-22. Issue: #3006. OpenSpec change: `alias-move-digest-3006`.

## What was verified
- The #2996 heal mechanism was structurally incapable of converging: run `45019438459` showed `docker buildx imagetools create` copying pin `vllm@sha256:b62be5450…` but pushing `sha256:55765cf1…` to `vllm:cuda` — `imagetools create` re-serializes the single `manifest.v2+json` pin into a `manifest.list.v2+json` index under a NEW digest, so the post-move probe can never equal the committed pin (measured 2026-11-22: the raw pin bytes hash exactly to the pin digest; the drifted alias names a manifest LIST with different layers).
- `scripts/engine_alias_move.py` now FETCHES the pin manifest verbatim (`docker buildx imagetools inspect --raw <repo>@<digest>`), hashes the fetched bytes locally and refuses to publish anything whose hash is not the pin, then PUTs the exact bytes to `<name>/manifests/<variant>` with the manifest's own mediaType as Content-Type (GHCR token exchange from `GHCR_LOGIN_TOKEN`/`GHCR_LOGIN_USER`), then verifies through the unchanged `engine_image._digest_http` probe.
- `tests/test_engine_alias_move.py` pins the mechanism with injected seams: happy path (fetch command, byte-identical PUT, mediaType, post-move MOVED), fetch-hash mismatch → zero PUTs, mediaType-less fetch → zero PUTs, refused PUT → no re-probe, fetch failure → no write/verify, contract refusals exit 2 with zero registry calls, and the wiring test pins both heal env vars plus the no-`imagetools create` rule. Targeted battery: 59 passed.
- `make -s check-workflows`, `make -s check-package-layers`, `make -s check-wiring`, `make openspec-validate NAME=alias-move-digest-3006` all rc=0.

## Key decision
The live `main` heal outcome (both lagging vllm cells green on the next scheduled `registry-liveness` run) is the landing record for this lane and is tracked by the post-#2996 sweep issue https://github.com/asimov-agent/llgenie/issues/3004 — this lane lands the mechanism, not the sweep.

## Current status
Mechanism + tests landed on `feat/alias-move-digest-3006`; the fleet gate's verdict is the next `registry-liveness` green on `main`.
