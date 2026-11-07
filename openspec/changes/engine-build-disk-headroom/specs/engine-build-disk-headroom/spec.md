# engine-build-disk-headroom

## ADDED Requirements

### Requirement: every engine-build cell has a fail-fast disk-headroom gate

An oversized CUDA/ROCm/prebuilt cell MUST free reclaimable disk before building (the docker/buildx
layer cache plus the big toolchain dirs), MUST measure free disk, and MUST fail fast with the df
line when free space is below the tunable `LLGENIE_DISK_FLOOR_GB` floor — a too-small runner reds
in seconds instead of building ~13 minutes then dying `no space left on device` mid-export (issue
#1893, run `42318302931` job `128236450274`).

WHEN the engine-build `build` job starts a cell
THEN it frees the docker/buildx layer cache and the big toolchain dirs, measures free disk, records
`FREE_DISK_GB`, and fails the step when the free space is below `LLGENIE_DISK_FLOOR_GB`.

#### Scenario: an under-disk runner fails fast at the gate

- **Given** the `Disk headroom` step in `engine-build.yml` with `LLGENIE_DISK_FLOOR_GB`
- **When** the runner's free disk is below the floor
- **Then** the step exits non-zero with the `df -h /` line and a `::error::` annotation naming the
  cell and the floor — the cell reds immediately, not after the build exhausts the disk
- **Test:** `test_every_cell_has_a_fail_fast_disk_headroom_gate` asserts the floor + `exit 1` +
  `docker builder prune` + `FREE_DISK_GB`; the gate fails on the base workflow and passes on the
  fixed one

### Requirement: the layer cache is freed before the build

The pre-build disk step MUST `docker builder prune -af` (and remove the remaining toolchain dirs)
so a previous oversized cell's giant image/layer cache becomes headroom instead of a guaranteed
ENOSPC.

WHEN the cell begins
THEN the docker/buildx layer cache is pruned before `make build-engine`.

#### Scenario: the giant layer cache is freed first

- **Given** the `Disk headroom` step
- **When** it runs
- **Then** `docker builder prune -af` and `rm -rf` of the oversized toolchain dirs precede the
  build
- **Test:** `test_disk_gate_frees_the_giant_layer_cache_before_the_build` asserts both are present
