# Proposal: alias-move-fetch-3010

## Why
Issue #3010. Since PR #3009 landed the byte-preserving alias heal, registry-liveness run `45040752698` on main `a3384331d` failed the heal step with a new failure class: `[alias-move] FAIL ghcr.io/asimov-agent/llgenie/vllm@sha256:1e74e680…: the fetched bytes hash to sha256:e3b0c442…` — `sha256(e3b0c442…)` is the hash of the EMPTY string, while the fetched manifest JSON is visibly streamed in the same step log. Mechanism: `move_alias` runs `docker buildx imagetools inspect --raw` through its default proc seam `proc.run_live`, and `proc.py` documents that `run_live` does NOT capture (`stdout`/`stderr` on the returned process are `None`). The live path therefore hashes `b""` 100% of the time and every heal fails the byte gate. Host proof that the contract is sound when the fetch captures: `inspect --raw …@sha256:1e74e680…` emits 8487 bytes whose `sha256sum` equals exactly the pin digest.

## What Changes
- `scripts/engine_alias_move.py`: the default fetch seam of `move_alias` becomes `proc.run_ok` (captures both streams, never raises), not `proc.run_live` (streams, captures nothing).
- `scripts/engine_alias_move.py`: an empty/None capture is refused with a named FAIL — `the fetch seam captured nothing` — printed BEFORE any hashing, so a wrong seam can never masquerade as a digest mismatch again.
- `tests/test_engine_alias_move.py`: regression tests — (1) the default fetch seam is the capture policy `proc.run_ok`; (2) a `run_live`-shaped seam (`stdout=None`) is refused with the named FAIL and ZERO manifest writes; (3) an end-to-end test driving the REAL `proc.run_ok` against a stub inspect command: the byte gate passes and the PUT body is byte-identical.

No spec-semantics change to the byte-identity contract from `alias-move-digest-3006`; this change makes the LIVE path of that contract actually capture the manifest.

## Impact
- Affected specs: `engine-alias-realignment` (ADDED requirement: capture-seam fetch + named empty-capture refusal)
- Affected code: `scripts/engine_alias_move.py`, `tests/test_engine_alias_move.py`
- Issue: #3010 (the PR closes it). Out of scope: none.
