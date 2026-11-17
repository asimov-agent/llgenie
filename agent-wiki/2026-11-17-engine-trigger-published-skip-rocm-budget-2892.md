# Engine-build-pr-trigger: published-skip, per-arch budgets, replacement cap (issue #2892)

## What was wrong

The pin-bump trigger's producer wait budget was a flat 60 minutes (`DEFAULT_MAX_WAIT = 60`), which a
cold ROCm cell cannot fit: run 44143247189 (`llama.cpp-laurentzuijdwijk` ROCm, head `8332018901`) was
still building past 61 min against the 60-min bound. Measured 2026-11-17 (Actions runs API): **6
trigger runs -> 5 completed/failure + 1 in_progress at 3h; 28 producer dispatches -> 15 success, 9
cancelled, 4 incomplete**. Re-pinned ROCm cells always reddened their trigger and each cancelled
producer spawned a replacement dispatch that re-queued at the back of the FIFO, feeding itself. The
four live engine-bump PRs (#2840, #2872, #2873, #2874) could not land.

## What changed

`scripts/engine_build_trigger.py` (the trigger workflow needed no change):

1. **Published-skip probe.** Before dispatching a producer for a cell, probe `ei.REGISTRY` for the
   cell's exact committed tag (`cpp.exact_tags`) with the may-arm's `_digest_http` manifest lookup. A
   cell whose tag resolves a manifest is concluded `PUBLISHED-SKIP` with no dispatch, so a
   reopened/sync'ed PR whose cells are published goes green in seconds. An unnameable tag (incl.
   `SystemExit` from an unknown variant) is never a published-skip decision — the cell dispatches.
2. **Per-arch-class wait budget.** `CLASS_WAIT_MIN`: `rocm`=150 min, `cpu`/`cuda`/`vulkan` keep 60.
   `_cell_wait_min(variant, explicit)` — an explicit `--wait-min` overrides every class; `main`'s
   `--wait-min` default is now `None` so the class default applies when not passed.
3. **Replacement cap.** `_await_cell` fires at most ONE replacement dispatch per (cell, trigger run)
   on a `cancelled` verdict, within the cell's REMAINING budget; a budget already spent withholds the
   replacement (`replace_cap`). A second cancellation fails the cell (never looped).

## Verification

- `tests/test_engine_build_trigger.py` reworked `_fake_gh` to model repeated dispatches (a fresh run id
  per `gh workflow run`) and a hermetic `ebt._digest`; four new acceptance tests: published-skip
  dispatch-0 rc-0, per-arch budgets (rocm=150 / others=60 / `--wait-min` overrides), cancelled→at-most-
  one replacement (2 dispatches, rc 1, cap named), and budget-exhausted withholds the replacement.
- Full module green: `25 passed`.
- OpenSpec change `engine-trigger-published-skip-rocm-budget` created (validated by CI's
  `openspec-validate`; the CLI image could not run in this container — no Docker daemon).

## Status

Implemented per the OpenSpec spec; the change is left uncommitted for the bot to commit and open the PR
that closes #2892 (producer flow, owner merges via the auto-merge job; never merged by the agent).
