# engine-build-cache-write-tolerates-missing-package

## ADDED Requirements

### Requirement: `--cache-to type=registry` is tolerant of a missing engine package

`_buildx()` MUST NOT add `--cache-to type=registry,ref=<cache_ref>` when the cache image does not
exist in the registry. It MUST probe the ref first (with `docker buildx imagetools inspect`) and,
when the image is absent, build **cold** rather than fail the cell with `not found`. When the
image IS present, the write MUST be emitted unchanged (the cache is seeded for the next run).

WHEN an unforced build targets a cache ref whose engine package is not on the registry
THEN the build runs cold (no `--cache-to`), records the decision with a printed note, and the
cell is not failed

#### Scenario: a never-published engine's cache write builds cold, not red

- **Given** `REGISTRY` set, `CACHE_WRITE=1`, and a cache ref whose image does not exist
  (`imagetools inspect` → rc 1)
- **When** `_buildx(tag, ctx, push=false, cache_ref)` runs an unforced build
- **Then** the buildx argv contains **no** `--cache-to` (and no `--cache-from`), and the absence
  is a printed note — the cell is not failed
- **Test:** `tests/test_engine_force_rebuild.py::test_a_missing_cache_image_builds_cold_not_red`

#### Scenario: a seeded cache is still written by the privileged run

- **Given** `REGISTRY` set, `CACHE_WRITE=1`, and a cache ref whose image exists
  (`imagetools inspect` → rc 0)
- **When** `_buildx(tag, ctx, push=false, cache_ref)` runs an unforced build
- **Then** `--cache-to type=registry,ref=<cache_ref>,mode=max` is emitted unchanged (the cache is
  seeded for the next run)
- **Test:** `tests/test_engine_force_rebuild.py::test_a_present_cache_image_still_writes_when_privileged`

### Requirement: the force, push, and read semantics are preserved

A forced build MUST still pass `--no-cache` and no `--cache-from` (real rebuild, issue #638). A
pushing build MUST push only the registry-qualified tag and keep the registry cache in and out.
The read-side tolerance (#1842) is unchanged.

WHEN `force=True` OR the build pushes OR the cache ref exists
THEN the write tolerance does not alter the existing behavior

#### Scenario: forced and push builds are unchanged

- **Given** a cache-tolerant `_buildx`
- **When** `force=True` or `push=True`
- **Then** behavior is as before the change (existing `test_engine_force_rebuild.py` force cases
  and `test_engine_skills.py::test_push_targets_only_the_registry_tag` pass)
- **Test:** `tests/test_engine_force_rebuild.py::test_a_forced_push_build_does_not_read_the_cache`