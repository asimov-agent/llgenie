# cache-write-package-probe — specs

## ADDED Requirements

### Requirement: Registry cache write eligibility is decoupled from the cache-ref read probe

The engine build seam SHALL decide the `--cache-to type=registry` write from a ladder, not from the
read side's single probe of the cache ref: when the cache ref exists the write is emitted; when the
cache ref is ABSENT the write is emitted if and only if the image package that the cache ref lives
under is published on the registry (the seeding case); the write is skipped only when that package
has never been published at all.

The package probe SHALL exchange an anonymous registry pull token and issue
`GET /v2/<package>/tags/list?n=1` for the package the cache ref names; a non-empty tags list means
published, and an absent package, an empty tag list, or an unreachable registry means not published.
The probe SHALL be consulted only when a cache write is being decided and the cache ref is absent,
and at most once per build.

Every outcome SHALL be printed, never a silent skip: `absent -> seeding it (package published)` when
the seeding write is added, and `cache write skipped; #1880` when the package is absent.

#### Scenario: a published package with an unseeded cache ref seeds the cache

- **Given** `REGISTRY` set, `CACHE_WRITE=1`, a cache ref whose image is absent
  (`imagetools inspect` → rc 1) and whose package IS published (`tags/list` non-empty)
- **When** `_cache_write_args(cache_ref)` decides the write
- **Then** it returns `["--cache-to", "type=registry,ref=<cache_ref>,mode=max"]` and prints the
  seeding note
- **Test:** `tests/test_engine_force_rebuild.py::test_cache_write_args_seeds_when_package_published`

#### Scenario: the seeding write reaches both build branches

- **Given** a cache ref that is absent while its package is published
- **When** `_buildx(..., push=true)` runs, and separately when `_buildx(..., push=false)` runs with
  `CACHE_WRITE=1`
- **Then** the buildx argv carries `--cache-to type=registry,ref=<cache_ref>,mode=max` on the push
  branch AND on the local branch, and no `--cache-from` on either
- **Test:** `tests/test_engine_force_rebuild.py::test_push_build_seeds_cache_to_for_published_package`,
  `tests/test_engine_force_rebuild.py::test_local_cache_write_build_seeds_cache_to_for_published_package`

#### Scenario: an unpublished package still builds cold (#1880 preserved)

- **Given** a cache ref whose image is absent AND whose package is absent (`tags/list` empty/404)
- **When** `_buildx(...)` runs on the push branch, or on the local branch with `CACHE_WRITE=1`
- **Then** the argv has no `--cache-from` and no `--cache-to`, the `#1880` note is printed, and the
  cell is not failed
- **Test:** `tests/test_engine_force_rebuild.py::test_a_missing_cache_image_builds_cold_not_red`,
  `tests/test_engine_force_rebuild.py::test_push_build_missing_cache_image_builds_cold_not_red`

### Requirement: the read side and the probe budget are unchanged

An absent cache ref SHALL still emit no `--cache-from`; a present cache ref SHALL still read and write
exactly as today. The package probe SHALL NOT run when the cache ref exists, when a build is forced,
or when the build exports no cache, so a build never issues more than one cache-ref probe and one
package probe.

#### Scenario: a present cache ref never triggers the package probe

- **Given** a cache ref whose image exists (`imagetools inspect` → rc 0)
- **When** `_cache_write_args(cache_ref)` decides the write
- **Then** the package probe is not called and `--cache-to` is emitted unchanged
- **Test:** `tests/test_engine_force_rebuild.py::test_cache_write_args_emits_cache_to_when_present`

#### Scenario: a forced or read-only build issues no package probe

- **Given** `REGISTRY` set and a cache ref whose image is absent
- **When** `_buildx(..., force=true)` runs, or `_buildx(..., push=false)` runs with `CACHE_WRITE` unset
- **Then** the package probe is never called and no `--cache-to` is emitted
- **Test:** `tests/test_engine_force_rebuild.py::test_no_package_probe_for_forced_or_readonly_build`
