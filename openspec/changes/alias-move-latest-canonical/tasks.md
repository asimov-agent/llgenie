# alias-move-latest-canonical — tasks

- [x] Extend `move_alias` so a verified canonical-variant move also PUTs the identical fetched
      manifest bytes to `/manifests/latest` and verifies `:latest` at the same pin digest, using
      `engine_image.engine_latest_variant` as the sole ownership rule.
- [x] Keep the four-field contract, byte-preserving fetch, mediaType, refusal rails and
      variant-only behaviour for non-canonical cells unchanged.
- [x] Hermetic unit proof in `tests/test_engine_alias_move.py` (fake `run`/`probe`/`put` registry
      seam, no engine run/build): canonical moves both tags byte-for-byte; non-canonical moves only
      the variant; a failed variant verification never publishes `:latest`.
- [x] Change note trio per #1123: agent-wiki note + `docs/changes.d/` fragment + regenerated index.
- [x] Gates at fix head: `make test-unit`, `make check-docs`, `make openspec-validate-all`,
      `make openspec-tasks-check`, `make bot-preflight`.
