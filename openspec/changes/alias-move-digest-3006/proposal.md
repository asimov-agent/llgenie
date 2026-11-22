# Heal alias lag with a digest-preserving manifest move (issue #3006)

## Why

The #2996 heal is mechanically broken: the registry-liveness run on `46b15838e1` (run `45019438459`) moved both lagging cells and still failed both — `vllm:cuda` pin `sha256:b62be545…` came back post-move as `sha256:55765cf1…`, `vllm:rocm` pin `sha256:1e74e680…` as `sha256:a23aeb82…`. Measured at the registry (`docker buildx imagetools inspect --raw`, 2026-11-22): the committed pin `vllm:3a4d82f5-4c1f3eee-cuda` is a plain `application/vnd.docker.distribution.manifest.v2+json` (keys `config`/`layers`), while what `docker buildx imagetools create` published on `:cuda` is an `application/vnd.docker.distribution.manifest.list.v2+json` (key `manifests`) — imagetools create ALWAYS re-serializes its input as a manifest list, so the new tag can never carry the pin digest, and the mover's own post-move verification (`alias digest == pin digest`, the contract the #2996 spec demands) can NEVER pass. Every liveness run now re-heals and re-fails the same cells — the fire-loop moved from build dispatches to heal failures.

A true alias move is byte-identity: fetch the pin manifest EXACTLY (`imagetools inspect --raw` returns the stored bytes; measured `sha256(raw) == pin`) and re-publish those same bytes on the `:<variant>` tag through the registry's manifest PUT. Same bytes ⇒ the registry stores the identical blob ⇒ the tag resolves to the identical digest.

## What Changes

- `scripts/engine_alias_move.py`: the move step replaces `docker buildx imagetools create` with a digest-preserving two-step manifest move:
  1. FETCH the pin manifest verbatim: `docker buildx imagetools inspect --raw <repo>@<digest>`; refuse (exit 1, zero writes) unless `sha256(fetched bytes)` equals the requested digest — a fetch that is not the pin is never published anywhere.
  2. PUT those exact bytes to `https://ghcr.io/v2/<name>/manifests/<variant>` with `Content-Type` taken from the manifest's own `mediaType` field, authenticated by a GHCR token exchange (`POST /token`, `GHCR_LOGIN_TOKEN` + `GHCR_LOGIN_USER` from the environment — the heal step already holds the login credential through `env:`, #361).
  3. Verify after the move exactly as before: re-resolve `:<variant>` through `engine_image._digest_http`; MOVED only when it equals the pin digest.
  Contract refusal (four fields, `sha256:<64 hex>`, committed-suffix agreement) is unchanged and still touches nothing. Stdlib-only (urllib/json/hashlib); the fetch keeps the `proc` subprocess seam, and the PUT is a seam parameter so the suite stays hermetic (no network in unit tests).
- `.github/workflows/registry-liveness.yml`: the heal step additionally exports `GHCR_LOGIN_USER: "${{ github.actor }}"` beside `GHCR_LOGIN_TOKEN` (env only, never `run:` text) so the mover's token exchange authenticates as the same principal the `docker login` already uses. The rest of the heal step (contract parse, publisher-in-flight deferral, per-cell `make engine-alias-move`, red-on-fail) is unchanged.
- `scripts/package-layers.json`: `engine_alias_move` stays in "CI entrypoints" with its stated edges (`engine_image`, `proc`).
- Tests (`tests/test_engine_alias_move.py`, updated in place): the happy path now pins the FETCH command, byte-identity of the PUT body vs the fetched manifest, the `mediaType` header agreement, the exact manifest-PUT target path, refusal of a fetch whose hash mismatches the pin (zero PUTs), a refused PUT (no re-probe), post-move digest mismatch, and all contract refusals. The gate→mover seam and wiring tests keep their assertions, extended to the two heal env vars.

## Impact

- `scripts/engine_alias_move.py` (move step rewritten), `tests/test_engine_alias_move.py` (updated in place), `.github/workflows/registry-liveness.yml` (one heal-step env line), `scripts/package-layers.json` (unchanged edges).
- The two live lag cells (`vllm:cuda`, `vllm:rocm`) heal on the next registry-liveness run of the merged tip (GitHub event on the merge push; no manual dispatch, no rerun) and read ALIAS OK on the same run's fleet gate.
- `make post-merge-live-check` reads the green run after landing.
- Issue #3004 (post-#2996 sweep) is satisfied by this landing: its deferred sweep exists because every liveness run since #3001 re-failed the same two cells.

Refs: issue #3006 (measured digests and run ids in its body), predecessor #2996 (the heal this corrects), tracked remainder #3004.
