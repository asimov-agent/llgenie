# 2026-11-12 — PR-trigger cell detection (issue #2590)

Issue: #2590 (out-of-scope half surfaced by #2553 / PR #2582). OpenSpec change: `pr-trigger-cell-detection`.

## What was verified

- **The gap, measured on the real #2582 data:** the trigger dispatched engine-build run 43248400389 with
  only `engine-build-vllm-cpu` while the change repinned the rocm cell
  (`vllm 3a4d82f5-db98981b-rocm -> 3a4d82f5-d04739cb-rocm`); the gate then red at
  `[pins] NOT PUBLISHED vllm:3a4d82f5-d04739cb-rocm (HTTP 404)` (unit log of run 43264350593, 17:16:31Z).
- **Cell-granularity detection:** `repinned_cells(base, root)` was run against PR #2582's real tree
  (`feat/vllm-rocm-base-access` worktree) with base `origin/main` and returned exactly
  `[('vllm', 'rocm')]` while the engine-deduped view stayed `['vllm']` — the may-arm verdict is
  unchanged (DEMO-rc=0).
- **Dispatch shape:** the trigger now sends `engine=<id>`, `push=true`, `arch=<variant>` per moved cell;
  the hermetic test `test_a_repinned_gpu_cell_is_dispatched_with_its_explicit_arch` asserts the fields
  `["engine=vllm", "push=true", "arch=rocm"]` end-to-end through the fake-gh harness, and
  `test_the_dry_plan_names_the_cell_arch_and_never_an_archless_dispatch` locks the dry plan to the cell
  shape. `test_repinned_cells_names_only_the_cell_whose_tag_moved` proves on a synthetic git tree that
  adding a rocm variant moves ONLY the rocm cell (`_image_inputs` hashes each variant's own params subset).
- **Hermetic gate:** `tests/test_engine_build_trigger.py tests/test_check_engine_pins_published.py
  tests/test_engine_image_matrix.py tests/test_ci_publish_order.py` → `99 passed, 1 deselected` in the
  test container with the unit marker (CELLTEST-rc=0).
- **Hermetic no-op path:** `make engine-build-pr-trigger BASE=origin/main BRANCH=feat/pr-trigger-cell-detection DRY=1`
  prints `no cell this change repins; nothing to dispatch` and exits 0 (DRY-rc=0);
  `make engine-build-pr-trigger-report BASE=origin/main` prints `[will] 0 repinned cell(s)` (REPORT-rc=0).

## Key decisions

- `repinned_engine_ids` stays the engine-deduped view DERIVED from `repinned_cells` — one comparison
  path, two granularities; the may-arm verdict can never loosen because the trigger narrowed.
- The params-FILE diff union stays in `repinned_engine_ids` (it catches params edits whose tag digest
  cannot be computed, e.g. unparseable copies) but the CELL dispatch only uses confidently computed
  cells.
- `DEFAULT_ARCHES` fallback in the trigger only applies to the `--engine` hand-selection (engine-level
  CLI use), never to the repin path: a repinned cell always names its own arch.

## Current status

Branch `feat/pr-trigger-cell-detection` off `origin/main`; implementation + tests + docs in; full
hermetic `make test-unit`, openspec validate, lane-preflight, and the PR are tracked in the issue/PR
thread.
