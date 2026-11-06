# engine-build-tolerate-missing-cache

## ADDED Requirements

### Requirement: `--cache-from type=registry` is tolerant of a missing cache image

`_buildx()` MUST NOT add `--cache-from type=registry,ref=<cache_ref>` when the cache image does
not exist in the registry. It MUST probe the ref first (with `docker buildx imagetools inspect`)
and, when the image is absent, build **cold** rather than fail the cell with `manifest unknown`.
When the image IS present, the read MUST be emitted unchanged (layers are reused). In every case
the privileged write (`--cache-to`) is unaffected.

WHEN an unforced build targets a never-seeded registry cache
THEN the build runs cold (no `--cache-from`), records the decision with a printed note, and still
writes `--cache-to` so the next run is warm

#### Scenario: a never-seeded cache builds cold, not red

- **Given** `REGISTRY` set and a cache ref whose image does not exist (`imagetools inspect` → rc 1)
- **When** `_buildx(tag, ctx, push=false, cache_ref)` runs an unforced build
- **Then** the buildx argv contains **no** `--cache-from`, contains `--cache-to` when
  `CACHE_WRITE=1`, and the absence is a printed note — the cell is not failed
- **Test:** `tests/test_engine_force_rebuild.py::test_a_missing_cache_image_builds_cold_not_red`

#### Scenario: a seeded cache is still read

- **Given** `REGISTRY` set and a cache ref whose image exists (`imagetools inspect` → rc 0)
- **When** `_buildx(tag, ctx, push=false, cache_ref)` runs an unforced build
- **Then** `--cache-from type=registry,ref=<cache_ref>` is emitted unchanged (unchanged layers are
  reused), and an unprivileged build stays read-only (no `--cache-to`)
- **Test:** `tests/test_engine_force_rebuild.py::test_a_present_cache_image_keeps_cache_from`

### Requirement: the force and push semantics are preserved

A forced build MUST still pass `--no-cache` and no `--cache-from` (real rebuild, issue #638). A
pushing build MUST push only the registry-qualified tag and keep the registry cache in and out.

WHEN `force=True` OR the build pushes
THEN the cache-read tolerance does not alter the existing behavior

#### Scenario: forced and push builds are unchanged

- **Given** an unforced cache-tolerant `_buildx`
- **When** `force=True` or `push=True`
- **Then** behavior is byte-for-byte as before the change (existing `test_engine_force_rebuild.py`
  force cases and `test_engine_skills.py::test_push_targets_only_the_registry_tag` pass)
- **Test:** `tests/test_engine_force_rebuild.py::test_a_forced_build_passes_no_cache_and_drops_cache_from`,
  `tests/test_engine_skills.py::test_push_targets_only_the_registry_tag`
