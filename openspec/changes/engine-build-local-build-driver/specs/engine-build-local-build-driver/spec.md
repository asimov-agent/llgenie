# engine-build-local-build-driver

## ADDED Requirements

### Requirement: a local build runs on the docker-container driver only when it exports a cache

A verification build (`push=false`) must not pay the docker-container driver's local export path —
it writes the whole image as a tar and then unpacks it into dockerd on top of the builder's own
content store, about 3x the unpacked image — unless that build actually exports a registry cache.
Measured on issue #1915: the `freetoken/rocm` cell ENOSPC'd mid-load with 107 GiB free on the
container builder (run `42326740375`) and went green on the docker driver with 104 GiB free (run
`41957934540`), for the same image at the same tag.

WHEN a local (non-pushing) build would export no registry cache — a `force` build, which consults
neither cache side, or a cell listed in `NO_CACHE_EXPORT`
THEN it MUST build on the `default` (docker) driver and pass no `--cache-from` / `--cache-to`.

AND WHEN a local build does export a registry cache
THEN it MUST stay on the active docker-container builder (only that driver can export one) and the
per-cell exemption MUST NOT apply.

#### Scenario: a forced verification build uses the docker driver

- **Given** `LLGENIE_CACHE_WRITE=1` and a `force` local build (no cache read, no cache write)
- **When** `make build-engine` runs its buildx call
- **Then** the command names `--builder default` and carries neither `--cache-from` nor `--cache-to`
- **Test:** `tests/test_engine_force_rebuild.py::test_a_forced_local_build_never_needs_the_container_driver`

#### Scenario: a cell that cannot afford the export builds on the docker driver

- **Given** an unforced local build of a cell listed in `NO_CACHE_EXPORT` with `LLGENIE_CACHE_WRITE=1`
- **When** `make build-engine` runs its buildx call
- **Then** the command names `--builder default`, carries no cache flags, and prints the reason
- **Test:** `tests/test_engine_force_rebuild.py::test_a_cell_that_cannot_afford_the_export_builds_on_the_docker_driver`

#### Scenario: an ordinary cell keeps its registry cache

- **Given** an unforced local build of a cell that is NOT listed in `NO_CACHE_EXPORT`
- **When** `make build-engine` runs its buildx call
- **Then** the build stays on the container builder and both `--cache-from` and `--cache-to` are present
- **Test:** `tests/test_engine_force_rebuild.py::test_a_cell_not_in_the_map_still_exports_its_cache`

#### Scenario: every listed cell is a real committed cell

- **Given** the committed `containers/engines/params/*.json`
- **When** each `NO_CACHE_EXPORT` key is looked up
- **Then** the engine ships that exact variant (no orphan key, no typo)
- **Test:** `tests/test_engine_force_rebuild.py::test_the_no_cache_export_map_names_a_real_committed_cell`
