# 2026-11-07 — engine-build: fail-fast disk-headroom gate for oversized CUDA/ROCm cells (issue #1893)

Issue: [#1893](https://github.com/asimov-agent/llgenie/issues/1893)
OpenSpec: `openspec/changes/engine-build-disk-headroom`
PR: [#1895](https://github.com/asimov-agent/llgenie/pull/1895)

## What changed

Main-head engine-build run `42318302931` (`workflow_dispatch`, head `faef07fa`) — cell
`engine-build-sglang-cuda` (job `128236450274`) — failed `no space left on device` writing
`/sgl-workspace/sglang/rust/target/release/deps/libimage-*.rlib`, twice (build + docker export),
despite 104G free before the build. sglang-cuda derives `FROM lmsysorg/sglang:v0.5.23` (prebuilt);
the derived-image write re-encodes the base's multi-GB baked tree, so it exhausts a flat 104G with
no way to predict it until the 13-minute build dies mid-export.

The pre-build `Free disk` step became a durable **`Disk headroom`** policy for every cell:

- frees the docker/buildx layer cache first (`docker builder prune -af`) plus the remaining big
  toolchain dirs (node_modules, powershell, pipx, mono, pip/uv/cargo/rustup caches);
- measures free disk (`df -B1 --output=avail /`), records `FREE_DISK_GB`, reports a notice;
- **fails fast** below the tunable `LLGENIE_DISK_FLOOR_GB` (30 GiB) floor with the `df` line — a
  too-small runner reds in seconds instead of building 13 minutes then ENOSPC.

## Why this shape

A one-off re-run cannot fix a disk-exhausting build; the defect is that the workflow had no
headroom budget for an oversized prebuilt-base cell. This is a durable disk-footprint/mount
policy for oversized cells (issue #1893 AC-2), never a "retry". No gate was weakened; nothing is
retried silently.

## Measured verification (this lane, at fix head `a5eaff63`)

- Two new tests lock the gate (`test_every_cell_has_a_fail_fast_disk_headroom_gate`,
  `test_disk_gate_frees_the_giant_layer_cache_before_the_build`) — **mutation-proved**: both FAIL
  on base `faef07fa` (the `Disk headroom` step is absent) and PASS on the fix head.
- YAML parses (container); `make check-workflows` RC=0; `test_engine_build_workflow.py` 13 passed;
  engine suite (timeouts/force-rebuild/pr-trigger) 30 passed.
- The gate's `df -B1 --output=avail /` + floor logic was exercised on this host (GNU df = the
  ubuntu-latest runner): measures free space and trips the floor correctly.

## Left open for the dispatcher

A green re-run of `engine-build-sglang-cuda` at the fix head is owned by the dispatcher lane
post-merge (the workflow reads its file from `main`; a fork-head dispatch cannot be targeted), and
recorded as the remaining acceptance box on #1893.
