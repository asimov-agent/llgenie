# Tasks — alias-move-digest-3006

## Implementation

- [x] `scripts/engine_alias_move.py`: replace the `imagetools create` move with the byte-preserving FETCH (`inspect --raw`) + local sha256 gate + manifest PUT (exact bytes, `mediaType` Content-Type, GHCR token exchange from `GHCR_LOGIN_TOKEN`/`GHCR_LOGIN_USER`), then the unchanged post-move `_digest_http` verification; contract refusals unchanged. (proven: pytest tests/test_engine_alias_move.py rc=0)
- [x] `.github/workflows/registry-liveness.yml`: heal step exports `GHCR_LOGIN_USER: "${{ github.actor }}"` beside `GHCR_LOGIN_TOKEN` (env only). (proven: make -s check-workflows rc=0)
- [x] `scripts/package-layers.json`: confirm `engine_alias_move` edges stay stated (`engine_image`, `proc`). (proven: make -s check-package-layers rc=0)

## Tests

- [x] `tests/test_engine_alias_move.py` updated in place: happy path pins fetch command, byte-identical PUT body, mediaType header, `<name>/manifests/<variant>` target; fetch-hash mismatch → FAIL with zero PUTs; refused PUT → FAIL without re-probe; post-move mismatch unchanged; contract refusals unchanged; wiring test extended to both heal env vars. (proven: pytest tests/test_engine_alias_move.py tests/test_check_engine_pins_published.py 59 passed rc=0)

## Verification (tick each with its replayable proof)

- [x] `make -s check-package-layers` exits 0. (rc=0)
- [x] `make -s check-workflows` exits 0 on the changed workflow. (rc=0)
- [x] `make -s check-wiring` exits 0. (rc=0)
- [x] targeted pytest of `tests/test_engine_alias_move.py` and `tests/test_check_engine_pins_published.py` exits 0. (59 passed, rc=0)
- [x] `make openspec-validate NAME=alias-move-digest-3006` exits 0. (rc=0)
