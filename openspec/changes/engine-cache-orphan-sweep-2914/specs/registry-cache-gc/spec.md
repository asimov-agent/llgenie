# registry-cache-gc

## ADDED Requirements

### Requirement: an audit target names the superseded fixed-name cache refs with no live producer

`make engine-cache-orphan-report` MUST list every fixed-name cache tag present in the org's
`llgenie/` container packages that the current producer seams no longer write. The live producer set
is derived from the ONE seams the builds call (`engine_image.cache_ref`, `ci_images.cache_ref`), so
the report returns zero orphans while the cache-keying changes (#2891/#2911) have not landed, and
names the superseded fixed tags once they land — with no second derivation to keep in sync.

WHEN the report runs and all tags it sees are still written by a current producer seam
THEN it prints zero orphans (`rc=0`) and a live fixed tag is never named for deletion

#### Scenario: zero orphans while the keying has not landed

- **Given** a registry whose `llgenie/` packages hold exactly the fixed cache tags the current
  producer seams still write (`engine_image.cache_ref` returns `:buildcache`/`:buildcache-<variant>`)
- **When** `cache_orphan_report.orphan_refs()` runs
- **Then** it returns an empty list (a live fixed tag is never proposed for deletion)
- **Test:** `tests/test_cache_orphan_report.py::test_zero_orphans_while_fixed_tags_are_still_live`

#### Scenario: a fixed tag no seam produces is an orphan

- **Given** a registry that also holds a fixed cache tag whose engine is not among the committed
  params (e.g. `llgenie/some-old-engine:buildcache-cuda`)
- **When** `orphan_refs()` runs
- **Then** that old engine's fixed tag, and only it, is reported; a helper's still-live
  `llgenie/test:buildcache` is not
- **Test:** `tests/test_cache_orphan_report.py::test_orphan_reported_only_when_tag_has_no_live_producer`

#### Scenario: the live producer set spans helpers, bases and cells

- **Given** the committed repo
- **When** `live_cache_refs()` runs
- **Then** it contains a helper ref (`llgenie/<name>:buildcache`), every base backend's
  `llgenie/base-<backend>:buildcache`, and every engine cell's `llgenie/<engine>:buildcache-<variant>`
- **Test:** `tests/test_cache_orphan_report.py::test_live_producer_set_covers_helpers_bases_and_cells`

#### Scenario: a sweep refuses to touch a live fixed tag

- **Given** the registry holds only a live fixed tag (`llgenie/test:buildcache`, still written by
  `ci_images.cache_ref`)
- **When** `orphan_refs()` runs
- **Then** that live tag is not returned, so a sweep could not delete it
- **Test:** `tests/test_cache_orphan_report.py::test_live_fixed_tag_is_never_proposed_for_sweep`

### Requirement: the producer build paths share ONE cache-ref derivation

`scripts/engine_image.py` MUST derive both the base and cell registry cache refs through a single
`cache_ref(image_name, variant)` function that `build_base` and `build` call, so the GC report and the
build write from the same source and the keying changes (#2891) have one seam to edit.

WHEN `build_base`/`build` construct `--cache-to type=registry`
THEN they call `engine_image.cache_ref` and the emitted ref is byte-identical to the pre-change fixed name

#### Scenario: the canonical build paths emit the same fixed refs

- **Given** the refactored `cache_ref` seam and the existing force/push/read cache tests
- **When** `make test-unit` runs the engine cache tests
- **Then** the emitted `--cache-to type=registry,ref=...:buildcache(...)` refs are unchanged and green
- **Test:** `tests/test_engine_force_rebuild.py` (existing, unchanged) and `tests/test_ci_images.py`
