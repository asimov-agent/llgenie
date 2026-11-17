# engine-trigger-published-skip-rocm-budget

## Why

The `engine-build-pr-trigger` "will" arm of the pin-bump gate (issue #1633) gives every dispatched
producer a flat 60-minute wait budget (`DEFAULT_MAX_WAIT = 60`). A ROCm cell build does not fit in
that window: run 44143247189 (`llama.cpp-laurentzuijdwijk` ROCm, head `8332018901`) was dispatched
18:00:59Z, its ROCm job started 18:24:26Z with nothing queued ahead, and was still building past 61
minutes at 19:25Z. Measured on 2026-11-17 (Actions runs API): **6 trigger runs for the 4 open engine
PRs -> 5 completed/failure, 1 in_progress at 3h**, **28 producer dispatches -> 15 success, 9
cancelled, 4 incomplete**. The FIFO feeds itself: a re-pinned ROCm cell always consumes its budget
and reddens its trigger, and a cancelled/expired producer triggers a replacement dispatch that
re-queues at the back.

## What changes

Three behaviours in `scripts/engine_build_trigger.py` (the trigger workflow itself needs no change —
the default per-class budget now applies):

1. **Published-skip probe.** Before dispatching a producer, probe GHCR for the cell's exact
   committed tag (the same ref/`_digest_http` probe the may-arm #1622 uses). A cell whose tag already
   resolves a manifest is concluded `PUBLISHED-SKIP` with no build. A reopened/sync'ed PR whose cells
   are already published goes green in seconds instead of re-dispatching the whole matrix.
2. **Per-arch-class wait budget.** A `rocm` cell (and any class whose cold-build p95 exceeds the flat
   bound) is awaited with `150` minutes against the `60`-minute default for `cpu`/`cuda`/`vulkan`. An
   explicit `--wait-min` overrides every class.
3. **Replacement cap.** A queued producer that concludes `cancelled` gets exactly ONE replacement
   dispatch per (cell, trigger run), and the replacement inherits the cell's REMAINING wait budget —
   so a cancellation storm can never re-queue the same cell beyond its per-class bound.

## Out of scope

- #2891 (exporting buildx layer caches so cold ROCm rebuilds shrink) — filed separately.
- The `engine-build-push` FIFO concurrency-group design (landing rules under the #178 discipline).
