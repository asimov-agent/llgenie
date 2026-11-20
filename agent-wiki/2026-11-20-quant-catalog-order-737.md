# 2026-11-20 — the quant catalog's cell order becomes a repository decision (issue #737)

`data/trending-quant-catalog.json` listed each `(model, engine)` cell's plans in whatever order
the live `sort=downloads` Hub search returned, so the same repository input regenerated the same
plan SET in a different ORDER (measured 2026-10-27 on `288c141`: `qwen3.8-flash-next-125b`/MLX,
same 14 plans, different sequence). #736 mitigated that by comparing SETS and NOTE-ing reorders;
#737 fixes the cause: the generator now chooses the order.

## What was verified

- `_model_catalog` writes each deduped cell through `_cell_order` — ascending `(size_gb, repo,
  path)` — and `carry_over()` re-sorts every cell it touches, so a kept plan lands where the
  repository order puts it, not appended after the freshly generated ones.
- `compare()` reclaimed the order it gave up: the committed cell holding the SAME plan set in a
  DIFFERENT order is now a FAILURE naming the cell and pointing at `make sync-quant-catalog`.
  The #769 keep-or-drop probe rules (reachable → note, 404/410 → failure) are unchanged.
- Live regeneration through the seam (`make sync-quant-catalog`): 93 models, 2139 links, 0 cells
  out of the new order. Diff vs the previously committed table: order-only except the drift the
  sync itself announces — 2 plans dropped (their LICENSE links answer 404), 12 plans recorded
  (MLX conversions published since the last weekly sync).
- `make check-quant-catalog` → rc=0 with the regenerated table (307 drift notes, no failures);
  with the OLD committed table it fails on 69 reorder cells — the flipped rule bites.
- Tests: `test_a_reordered_cell_is_a_failure_once_generation_is_reproducible` (flipped),
  `test_a_cell_is_generated_in_repository_order_whatever_order_the_hub_returns`,
  `test_two_replays_of_the_recorded_answers_are_byte_identical`,
  `test_the_quant_range_is_sorted_by_size_whatever_order_the_row_lists` (consumer pin: the pick
  ranks by size, the row order is presentation),
  `test_the_carried_over_plan_lands_in_the_cells_repository_order`.

## Key decisions

- The sort point is the generator (one place), not the Hub candidate lists: a cell is identical
  whatever order the search returned it in.
- A GGUF cell's repo SELECTION stays Hub-driven (`gguf_repo()` ranks `sort=downloads`
  candidates); #737 governs the order of the plans a cell lists, not which repo wins.
- The sorted table must land in the same PR as the flip: `check-quant-catalog` runs on every PR,
  so code-first would leave `main` red until the weekly sync — the regenerated
  `data/` + fixture + Hub snapshot ride with the code, mirroring the #2846/#2906 lanes.

## Current status

OpenSpec change `quant-catalog-order-737` validated; lane pushed with `closes #737`;
the issue's AC-2 wording was corrected in the same pass (data lands with the code, not later).
