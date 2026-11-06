# Tasks

- [x] `engine_image.py::_buildx()` reads `--cache-from type=registry` only when the cache image exists: new `_cache_read_args(cache_ref)` probes it with `docker buildx imagetools inspect` and returns `[]` (cold build, printed note) when absent; both the local read path and the push path use it.
- [x] A regression test proves a never-seeded cache builds cold: `--cache-from` absent, `--cache-to` present when `CACHE_WRITE=1` (`tests/test_engine_force_rebuild.py::test_a_missing_cache_image_builds_cold_not_red`); a seeded cache still reads (`::test_a_present_cache_image_keeps_cache_from`).
- [x] Existing behavior preserved: `tests/test_engine_force_rebuild.py` force/push cases and `tests/test_engine_skills.py::test_push_targets_only_the_registry_tag` (locates the build argv by `--push`, robust to the new probe call) stay green — 183 passed across force_rebuild / image_matrix / ci_images / engine_skills / engine_binary_flags.
- [x] Docs trio: `docs/changes.d/2026-11-06-engine-build-tolerate-missing-cache.md` (one table row) + `agent-wiki/2026-11-06-engine-build-tolerate-missing-cache.md` narrative + regenerated `CHANGES.md`; `check_docs.py check` green.
- [x] PR body carries `AGENTS:`/`BASE:` (#792) and `closes #1842`; normal review flow (#1644 acceptance write-back, owner merges). No merge/arm (#1088).
