# The quant catalog is emitted in an order the repository chooses

## Why

`data/trending-quant-catalog.json` lists each `(model, engine)` cell's plans in whatever
order the live Hub search returned at generation time (`mlx_repos()`/`tensorfold_repos()`
query `sort=downloads`). The same repository input therefore regenerates the same plan SET
in a different ORDER as download counts move, so the committed table is not reproducible
from the repository alone — measured 2026-10-27 on `main` (`288c141`): `qwen3.8-flash-next-125b`/MLX
regenerated as the same 14 plans in a different sequence. The gate absorbed the chaos by
comparing SETS only and NOTE-ing the reorder (#736), which was the mitigation, not the fix
(issue #737).

## What changes

- `scripts/gen_trending_quant_catalog.py::_model_catalog` sorts each cell's plans into a
  repository-chosen order — `(size_gb, repo, path)`, ascending — after dedupe. The table
  order is then a decision in the repository, not a live ranking; a sync twice in a row on
  an unchanged Hub is byte-identical.
- `compare()` reclaims the order it gave up: when the committed cell and the fresh
  generation hold the SAME plan set in a DIFFERENT order, that is now a FAILURE naming the
  cell (the generation is reproducible, so the committed table must carry it), not a NOTE.
- The committed table and its Hub snapshot are regenerated once under the new rule via the
  existing `make sync-quant-catalog` seam (a `data/` + fixture change, like #2846/#2906).
- Tests: the reorder scenario flips from note to failure; a new determinism test states the
  rule (shuffled Hub candidates -> byte-identical payload); a consumer test states that
  `engine_supported_quants` ranks by size, independent of the row's list order.

## Out of scope

- The #769 keep-or-drop probe for plans the search stopped returning — unchanged.
- The pick's quant choice (`pick_quant` takes the largest that fits by explicit size
  comparison) — unchanged; the order of the row is documented as presentation, not rank.
