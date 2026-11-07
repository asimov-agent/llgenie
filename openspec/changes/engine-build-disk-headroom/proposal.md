# engine-build-disk-headroom — fail-fast disk-headroom gate for oversized CUDA/ROCm cells

## Why

Main-head engine-build run `42318302931` (`workflow_dispatch`, head `faef07fa`) — cell
`engine-build-sglang-cuda` (job `128236450274`) — FAILED with `no space left on device` writing
`/sgl-workspace/sglang/rust/target/release/deps/libimage-*.rlib`, twice (build + docker export),
despite 104G free before the build (job's own `df -h /`). sglang-cuda derives `FROM
lmsysorg/sglang:v0.5.23` (prebuilt), whose baked `/sgl-workspace/.../rust/target` tree is re-encoded
as the derived image's layers are written and exported — a CUDA base plus that tree exceed the
flat 104G the pre-build step left. The old `Free disk` step had **no floor gate**, so a too-small
runner spent ~13 minutes building then died mid-export with ENOSPC — an unfixable-by-retry defect.

## What changes

`.github/workflows/engine-build.yml`'s pre-build `Free disk` step becomes a durable **`Disk
headroom`** policy for every cell:

- frees the docker/buildx layer cache first (`docker builder prune -af`) plus the remaining big
  toolchain dirs (`node_modules`, `powershell`, `pipx`, `mono`, pip/uv/cargo/rustup caches);
- measures free disk (`df -B1 --output=avail /`), records `FREE_DISK_GB` to the step output and a
  notice annotation;
- **fails fast** with the `df` line when free space is below the tunable `LLGENIE_DISK_FLOOR_GB`
  (30 GiB default) floor — a too-small runner reds in seconds with a readable df verdict instead of
  a 13-minute build that dies mid-export.

Two tests (`test_every_cell_has_a_fail_fast_disk_headroom_gate`,
`test_disk_gate_frees_the_giant_layer_cache_before_the_build`) lock the gate and mutation-prove it
(FAIL on base `faef07fa`, PASS on the fix head). This is a durable disk-footprint policy for
oversized-build cells (AC-2), **not a one-off re-run**.

## Out of scope

- Reducing the size of `lmsysorg/sglang:v0.5.23` itself (a prebuilt upstream base; the engine
  internals are the engine lane's).
- The `mlx-cpu` host-verify serve timeout in the same run — separate defect (#1894, separate PR).
- Any other cell's build footprint.

## Who

ci-pipelines-maintainer (this lane owns the engine-build workflow's disk/mount policy).
