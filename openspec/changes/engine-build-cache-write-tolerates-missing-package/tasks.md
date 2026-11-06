# Tasks

- [x] `engine_image.py::_buildx()` writes `--cache-to type=registry` only when the cache image exists: new `_cache_write_args(cache_ref)` probes it with `docker buildx imagetools inspect` and returns `[]` (cold build, printed note) when absent; both the local `CACHE_WRITE=1` path and the push path use it.
- [x] A regression test proves a never-published engine's cache write builds cold: `--cache-from` AND `--cache-to` absent when the probe finds no cache image (`tests/test_engine_force_rebuild.py::test_a_missing_cache_image_builds_cold_not_red`); a seeded cache still reads AND writes when privileged (`::test_a_present_cache_image_still_writes_when_privileged`).
- [x] Existing behavior preserved: `tests/test_engine_force_rebuild.py` force/push cases and `tests/test_engine_skills.py::test_push_targets_only_the_registry_tag` stay green — 75 passed across force_rebuild / image_matrix / ci_images.
- [x] Docs trio: `docs/changes.d/2026-11-07-engine-build-cache-write-tolerates-missing-package-1880.md` (one table row) + `agent-wiki/2026-11-07-engine-build-cache-write-tolerates-missing-package-1880.md` narrative + regenerated `CHANGES.md`; `check_docs.py check` green.
- [x] PR body carries `AGENTS:`/`BASE:` (#792) and `closes #1880`; normal review flow (#1644 acceptance write-back, owner merges). No merge/arm (#1088).
