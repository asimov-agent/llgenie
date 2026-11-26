# Engine bump fan-out: every matrix variant reaches the producer

## Why

Issue #3066. A llama.cpp bump must prove EVERY variant `make -s engine-build-matrix ENGINE=llama.cpp`
lists — cpu/cuda/rocm/vulkan (issue #107). At PR #3033 (llama.cpp → `23924232`) head
`cf5208ba2d3f3ca3fa07603d746eb1395f5b1011` three of the four reported and the fourth never reached the
producer at all (measured 2026-11-25):

- `engine-build-llama.cpp-cpu` run 45243227657 `success`
- `engine-build-llama.cpp-cuda` run 45253760866 `success`
- `engine-build-llama.cpp-rocm` run 45264268556 `success`
- `engine-build-llama.cpp-vulkan` — **zero** check runs; no dispatch ever named it

Two shapes in `scripts/engine_build_trigger.py` produce that, and both are visible in the code:

1. **Serial dispatch.** `check()` loops `for e, v in sorted(cells)` (line 388) and calls
   `_dispatch_and_wait` (line 400), which dispatches a cell AND awaits that cell's verdict before it
   returns. The next cell is dispatched only after the previous cell's producer concludes, so a cell's
   wall time is `sum(previous cells' producer time) + its own` — not its own.
2. **`sorted()` puts the tail variant last.** Variants sort cpu, cuda, rocm, vulkan: the variant with no
   per-arch budget is dispatched LAST, behind the variant with the longest measured build
   (`WAIT_MIN_BY_ARCH = {"rocm": 150}` over `DEFAULT_MAX_WAIT = 60`).

The producer cannot absorb this: every `push=true` dispatch joins ONE global FIFO
(`engine-build.yml:90`, concurrency group `engine-build-push`, `cancel-in-progress: false`), so a queued
cell waits behind the runs the trigger itself just queued. With the #2892 budgets a llama.cpp wave is
60 + 60 + 150 + 60 = 330 min of serial queue against a 250-min trigger job window
(`engine-build-pr-trigger.yml:167`): the run is cancelled mid-await and the variant behind rocm never
gets its dispatch. `make engine-bump-restamp` then reads that head and flags the bump `unproven`
(`scripts/engine_bump_restamp.py:285-286` "no engine-build-llama.cpp-vulkan check run reported …",
:446-448 `SKIP=unproven`), which is #3066's third acceptance item.

## What Changes

1. **Split the fused seam** (all logic stays in this one script, per #917): `_dispatch_and_wait` becomes
   `_dispatch_cell` (dispatch + name the NEW run, #964 discipline, #2089 refusal text) plus
   `_await_cells`/`_await_cell_once` (one shared poll loop that carries every terminal rule the fused
   version had: #1931 cancelled/skipped terminal, #1994 success terminal, #2059 404 re-resolution, #1860
   push-group-holder naming, wall-clock bound).
2. **Fan out before awaiting**: `check()` probes published-skip for every repinned cell, dispatches
   EVERY unpublished cell, and only then awaits verdicts — so the queue holds the cell rather than the
   trigger's own serial loop.
3. **Dispatch the cheap cells first**: dispatch order is ascending wait budget, so rocm (150 min) no
   longer stands in front of the variant that has no class budget. Alphabetical order stays the
   *reporting* order.
4. **Queue-aware bound**: a fan-out cell's bound is `min(FANOUT_MAX_MINUTES = 240, max(budget,
   sum(budgets)))` when the wave dispatches more than one cell; a single-cell wave and an explicit
   `--wait-min` keep their exact bound, so every #2892 test stays meaningful. 240 sits under the
   measured 250-min job window so the *script* ends the wait and names the stall instead of GitHub
   killing the job mid-await; the workflow timeout is deliberately NOT raised.
5. **Name the omission**: when a dispatched variant ends expired / stalled / dispatch-refused, the
   trigger prints a `MISSING VARIANT` line naming engine, variant, reason and the readable run id, and
   says the bump PR body must carry it as `## Not covered` (the shape
   `scripts/engine_bump_restamp.py:331-340` already writes from `--deferred ENGINE=ISSUE`) — never a
   tick the head cannot back.
6. **Replacement cap unchanged**: at most ONE replacement dispatch per cancelled/expired cell, awaited
   on the carried budget (`budget * REPLACEMENT_FACTOR − consumed`, floor `REPLACEMENT_MIN_WAIT`).

## Impact

- Affected capability: `engine-bump-image-fanout` (spec delta in `specs/`).
- Affected code: `scripts/engine_build_trigger.py` (`check`, new `_dispatch_cell`/`_await_cells`),
  `tests/test_engine_build_trigger.py` (the seam the tests monkeypatch changes shape),
  `tests/test_engine_bump_restamp.py` (all-green-wave tick proof), docs (CHANGES.md, docs/changes.d/,
  agent-wiki entry).
- No new CI leg, no workflow timeout change, no change to the producer matrix or its concurrency group.
