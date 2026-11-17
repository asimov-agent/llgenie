# trigger-wait-budget-2892

## Why

The `engine-build-pr-trigger` lane waits on every dispatched producer with one flat 60-minute budget
(`DEFAULT_MAX_WAIT = 60`, `scripts/engine_build_trigger.py:70`) and re-dispatches a cell from every
fresh trigger run even when its exact content-tag is ALREADY published. Measured on 2026-11-17 across
the four open engine-bump PRs (#2840, #2872, #2873, #2874), 14:00-19:25Z: 6 trigger runs -> 5
completed/failure + 1 grinding 3h (44125529310); 28 producer dispatches -> 15 success / 9 cancelled /
4 incomplete, for ~15 distinct cells. A cold ROCm cell does not fit 60 min at all: run 44143247189
(head `8332018901`) was dispatched 18:00:59Z, its ROCm job started 18:24:26Z with NOTHING queued ahead,
and was still building past 61 minutes at 19:25Z. A cancelled/expired producer ends the trigger red;
the next reopen/re-trigger re-fires the FULL matrix, re-publishing cells that are already in GHCR and
re-queuing at the back of the `engine-build-push` FIFO — the queue feeds itself. Issue #2892.

## What Changes

engine-build-trigger capability:

- The trigger SHALL probe the may-arm's publish check (exact tag -> registry manifest, the same
  `check_engine_pins_published`/`engine_image._digest_http` logic the merged gate uses) for every
  repinned cell BEFORE dispatching. A cell whose exact tag already resolves a manifest is a
  PUBLISHED-SKIP: printed with its tag, never dispatched, and a pass whose every cell is
  published-skip exits 0 having dispatched nothing. `report`/`--dry` stay network-free.
- The wait budget SHALL be per-arch instead of one flat bound: `WAIT_MIN_BY_ARCH = {"rocm": 150}`
  (covers the measured >=61-min cold build plus queue headroom) over `DEFAULT_MAX_WAIT = 60` for the
  other classes; an explicit `--wait-min` overrides every class exactly as today. The FAIL line names
  the actual bound that expired.
- A producer that ends `cancelled`/`skipped` SHALL get AT MOST ONE replacement dispatch per cell per
  trigger run, with the carried budget: the cell's total bound is `budget * REPLACEMENT_FACTOR`
  (REPLACEMENT_FACTOR = 2) minus what the cancelled attempt consumed; if the replacement also fails,
  the FAIL line names that the single permitted replacement failed and no further dispatch happens
  in this run. A cancelled dispatch never re-dispatch when the remaining carried budget is exhausted.

## Impact

- `scripts/engine_build_trigger.py` (constants, `_published`, `_wait_budget`, replacement step in `check`)
- `tests/test_engine_build_trigger.py` (new tests published-skip x2, per-arch budgets x2, replacement cap/carried budget x2)
- No workflow, Makefile, or producer change: the lane already invokes the script with no `--wait-min`,
  so the new per-arch defaults apply automatically.
- Related issue #2891 (cold-base buildx cache export) attacks the build side of the same episode; this
  change is the wait/dispatch side.
