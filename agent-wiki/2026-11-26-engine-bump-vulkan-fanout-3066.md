# 2026-11-26 — the bump trigger fans out its variant wave and names the variant it lost (issue #3066)

## What was verified against the issue

- The gap is reproduced in the issue's own numbers (PR #3033 head `cf5208ba2d3f3ca3fa07603d746eb1395f5b1011`,
  measured 2026-11-25): `engine-build-llama.cpp-cpu` (45243227657), `-cuda` (45253760866) and `-rocm`
  (45264268556) all `success`, while `engine-build-llama.cpp-vulkan` has **zero** check runs. The matrix
  this repo generates asks for four variants (`make -s engine-build-matrix ENGINE=llama.cpp`), so the head
  was green with one variant unproven.
- The serial shape was read at source before the fix: `check()` dispatched a cell and awaited its verdict
  before the next cell (`_dispatch_and_wait`), `sorted()` put vulkan last behind rocm — the one arch with a
  class budget (`WAIT_MIN_BY_ARCH = {"rocm": 150}` vs `DEFAULT_MAX_WAIT = 60`) — and every `push=true`
  dispatch joins the single global `engine-build-push` FIFO (`engine-build.yml:90`,
  `cancel-in-progress: false`), so a llama.cpp wave was 60 + 60 + 150 + 60 = 330 min of serial queue against
  the 250-min trigger job window (`engine-build-pr-trigger.yml:167`).
- Fan-out seams in `scripts/engine_build_trigger.py` (no logic left the script, #917): `_dispatch_cell`
  (dispatch + name the NEW run, #964/#2089) and `_await_cells`/`_await_cell_once` (one shared poll loop
  carrying the #1931/#1994/#2059/#1860 rules). `check()` now probes published-skip for every repinned cell
  (#2892), dispatches EVERY unpublished cell, and only then awaits verdicts — the FIFO holds the cell, not
  the trigger's own loop. Reporting stays alphabetical; dispatch order is
  `sorted(to_dispatch, key=lambda c: (_wait_budget(c[1], wait_min), c[0], c[1]))`, so rocm is last
  (#2590 explicit-arch rule kept).
- Queue-aware bound: `FANOUT_MAX_MINUTES = 240` (under the measured 250-min job window) and `_fanout_bound`
  = `min(FANOUT_MAX_MINUTES, max(cell_budget, sum(wave_budgets)))`. A single-cell wave and an explicit
  `--wait-min` keep their exact bound — nothing is widened, and no workflow timeout was raised.
- Failure taxonomy + gap line: a dispatched cell that ends guard-refused / cause-failed / dispatch-never-
  started (#2089) / expired (incl. the `unresolved_404` poll race #2059 and the `stalled_behind`
  push-group-holder read #1860) / any non-success conclusion prints
  `MISSING VARIANT engine=<e> variant=<v> reason=<…> run=<id>` plus the obligation to carry the gap in the
  bump PR body as `## Not covered` — never a tick. The replacement cap stays: at most ONE replacement per
  cancelled/expired cell, awaited on the carried budget (`bound x REPLACEMENT_FACTOR - consumed`, floor
  `REPLACEMENT_MIN_WAIT`), never for a guard refusal (#2892).
- Tests (`tests/test_engine_build_trigger.py`, `tests/test_engine_bump_restamp.py` — 71 passed at this head):
  fakes repointed at `_dispatch_cell`/`_await_cells`/`_await_cell_once` recording each awaited cell's
  `budget`/bound, plus `test_a_single_cell_wave_keeps_its_class_budget_and_a_wide_wave_caps_at_the_job_window()`,
  `test_a_multi_variant_wave_queues_every_producer_before_awaiting_any_verdict()`,
  `test_the_arch_filter_narrows_the_wave_without_widening_its_bound()`,
  `test_a_stalled_rocm_tail_expiry_names_the_push_group_holder_and_files_a_missing_variant()`,
  `test_the_missing_variant_report_is_not_a_tick_even_when_the_other_cells_are_green()` and
  `test_a_green_wave_ticks_the_image_item_with_every_variant_run_id()` (four readable run ids, no variant gap).
- Gates measured at this head: `pytest tests/test_engine_build_trigger.py tests/test_engine_bump_restamp.py -q`
  71 passed; `make test-unit` rc=0 — 4529 passed / 13638 deselected / 0 skipped in 1434.50 s (23:54).

## Decisions

- **Dispatch-then-await, not dispatch-and-wait.** A `push=true` producer can only ever join the one
  `engine-build-push` FIFO, so the only way a four-variant bump costs less than the sum of its builds is to
  queue the whole wave up front. That turns the wait bound into a queue property, which is why the bound is
  now wave-aware instead of per-cell.
- **Ascending budget order, deliberately.** The cell most likely to run out of time (rocm, 150 min) goes to
  the tail of the FIFO; the variant with no class budget (vulkan) can no longer be starved by it. Reporting
  order stays alphabetical so the log stays diffable.
- **240, not "unbounded".** Raising the bound past the job window would have moved the failure from a named
  `MISSING VARIANT` to GitHub cancelling the trigger mid-await — the exact silence #3066 is about. The cap
  keeps the script in charge of the verdict.
- **A missing variant is a `## Not covered` obligation, never a tick.** The stamp (`SKIP=unproven`) and the
  trigger now say the same thing in the same words, so a reviewer cannot read a green lane as four builds.
- Out of scope, filed as its own issue: the live read — the next llama.cpp bump wave (or
  `make engine-bump-restamp PR=3033`) showing `engine-build-llama.cpp-vulkan` green at its head, or its gap
  named with a run id in that PR body (#3073). Engine image builds stay in the CI lane.

## Current status

Branch `engine-bump-vulkan-fanout` (off `origin/main`), OpenSpec change `engine-bump-vulkan-fanout`, issue
#3066. Issue body, PR body, OpenSpec change and code carry the same goal; the live-wave half is #3073.
