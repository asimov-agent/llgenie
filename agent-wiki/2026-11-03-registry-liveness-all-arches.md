# registry-liveness sweeps every backend (issue #1652)

**Date:** 2026-11-03 · **Branch:** `fix/1652-registry-liveness-all-arches` · **Related:** #1365, #1675

## What changed

`scripts/check_engine_launchers.py` grew `--arch all`, which sweeps **every** backend
(`engine_image.CI_VARIANTS` = cpu/cuda/rocm/vulkan) in one run instead of only the host's. The
registry-liveness monitor (`.github/workflows/registry-liveness.yml`) now passes `ARCH=all`, so a
committed engine pin whose image was never published reds the gate the same whether it is a cpu pin
or a cuda pin.

## Why

Issue #1365's class ("a committed engine pin whose image was never published passes every committed
CI") was only half-closed: `registry-liveness.yml` ran `make check-engine-launchers CHECK_REGISTRY=1`
with **no `--arch`**, so `check_engine_launchers.py` fell back to `detected_arch()` — `cpu` on a
GitHub-hosted runner. A committed novel-but-unpublished **cuda** pin therefore never produced a
`NOT PUBLISHED` line and never redded the monitor, even though `var iant`-specific images 404'd on
GHCR. The four cuda pins at #1652 are the concrete exposure (404 measured 2026-11-03).

## Design

- `--arch all` is **derived** from `engine_image.CI_VARIANTS`, not a second copy of the arch list —
  a new backend is swept the day it is added, not when a list in the workflow is edited.
- The default stays single-arch (`detected_arch`), so `ci-unit`'s hermetic `check-engine-launchers`
  (no network) is unchanged.
- `variant_for` already drops `ei.DISABLED` cells, so the wider sweep cannot false-red a disabled
  cuda/rocm cell.

## Verification

- `test_arch_all_sweeps_every_backend_and_names_a_cuda_unpublished` — with a stub `docker` whose
  manifest lookup misses, `--arch all --check-registry` exits 1 and prints `(arch cuda)` +
  `NOT PUBLISHED` (the host-only default never reaches cuda, and the pre-widening script fails the
  test — the guard provably catches the bug before the fix).
- `test_the_liveness_workflow_drives_the_sweep_of_every_backend` — asserts the workflow passes
  `ARCH=all`, so the widening cannot silently un-wire.
