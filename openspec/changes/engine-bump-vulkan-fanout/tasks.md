# Tasks — engine-bump-vulkan-fanout (#3066)

## 1. Fan out the bump dispatch (`scripts/engine_build_trigger.py`)

- [x] 1.1 Split `_dispatch_and_wait` into `_dispatch_cell` (dispatch + name the NEW run, #964/#2089) and
      `_await_cells`/`_await_cell_once` (shared poll loop carrying #1931, #1994, #2059, #1860 rules and the
      wall-clock bound) — no logic moved out of the script (#917).
- [x] 1.2 `check()`: probe published-skip for every repinned cell, dispatch EVERY unpublished cell, then
      await all verdicts in the shared loop; report in alphabetical order.
- [x] 1.3 Dispatch order = ascending per-arch wait budget (`_wait_budget`), so rocm cannot stand in front
      of a variant with no class budget; keep the explicit-arch dispatch rule (#2590).
- [x] 1.4 Add `FANOUT_MAX_MINUTES` (< the 250-min trigger job window) and `_fanout_bound`: wave bound =
      `min(FANOUT_MAX_MINUTES, max(budget, sum(budgets)))`; single-cell wave and explicit `--wait-min`
      keep their exact bound.
- [x] 1.5 Keep the replacement cap (#2892): ONE replacement per cancelled/expired cell on the carried
      budget, floor `REPLACEMENT_MIN_WAIT`, never for a guard refusal.
- [x] 1.6 Emit the `MISSING VARIANT` line for a cell that ends expired / stalled / dispatch-refused,
      naming engine, variant, reason, run id and the `## Not covered` obligation.

## 2. Tests

- [x] 2.1 Repoint the `tests/test_engine_build_trigger.py` fakes at the new seams and record each awaited
      cell's `budget` / bound so the #2892 assertions stay exact.
- [x] 2.2 Fan-out test: a four-variant wave dispatches four producers before any verdict is awaited, in
      ascending-budget order (cpu, cuda, vulkan, rocm).
- [x] 2.3 Tail-variant test: the last cell in a wave ends named by its fan-out bound, the producer run id,
      its last status and the push-group holder, and carries the `MISSING VARIANT` line.
- [x] 2.4 Bound tests: `--wait-min` is not widened; a single dispatching cell keeps its class bound.
- [x] 2.5 `tests/test_engine_bump_restamp.py`: a head whose cpu/cuda/rocm/vulkan producers are all green
      ticks the image item with four readable run ids and reports no variant gap (`unproven` stays 0).

## 3. Verify before ship

- [x] 3.1 `make test-unit` passes with zero skips on the branch head (record the counts).
- [x] 3.2 `make lint`, `make check-wiring`, `make check-docs` and `make check-ci-discipline` pass on the
      branch head.
- [x] 3.3 `make openspec-validate NAME=engine-bump-vulkan-fanout` exits 0.
- [x] 3.4 After rebasing onto the freshest `origin/main`: `make lane-preflight` prints `preflight: OK`.
