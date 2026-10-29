# The card gate reads measured evidence, and a card's list is the published tier ranking

**Issue:** #669 (`agent:implement`) · **Branch:** `fix/669-card-gate-vram` ·
**OpenSpec change:** `card-gate-measured-vram` · **PR:** see the branch's pull request.

## What was wrong (measured, vendored 2026-10-27 store, 112 rows)

`fits()` compared the card with the *declared* `vram_min` only — the half PR #732 landed — and
`trend_list()` returned the store in the order the FILE happened to be in (upstream's global
"Most loved" ranking). Both were measured wrong at the sizes the product targets:

- at an 8 GB card, `Qwen3.8-27B` was absent, although the store records a run on **4 GB VRAM +
  32 GB system RAM** (14.06 t/s) and upstream places it first in its own `### Up to 8 GB` table;
- 38 rows were admitted at 8 GB against the 47 the store's evidence supports;
- the 8 GB order was `Bonsai 2 9B`, `Qwen3.6-35B-A3B`, … where upstream publishes
  `Qwen3.6-35B-A3B`, `Bonsai 2 9B`, …

## What the change does

- `fits()` = **measured evidence**: a measurement that ran on a card ≤ N (`engines[].hardware`,
  a datacenter part never counts), else `vram_min` ≤ N, else the stated `weight_gb` ≤ N (the
  `weights-only` fit); `vram_tier` decides only for a row that states none of them. The RAM
  floor is read from the ADMITTING evidence — a run's own `system_ram_min`, else the RAM its
  hardware names — because that is the run being told about (`footprint()`'s "the measurement's
  own value wins").
- `trend_list()` = the vendored README's `### Up to N GB` **tier-local** ranking for the card,
  then the rows it does not rank (no post in the window: they still fit) in the store's own
  trend order. A card above 48 GB reads the 48 GB table (the largest published).
- `trend_key()` gained the store's own tie-break (peak t/s) and an id tie-break, and the
  remainder is sorted by it: the store's **file position is never read**, so a reordered or
  append-only store produces the same list. Measured: the committed order is non-decreasing
  under the key's stated fields for **112 of 112** rows (11 tie groups, no trend signal at all,
  are broken deterministically by id).

## Verified

| check | result |
|---|---|
| every model the README's `Up to 8/12/16/24/32/48 GB` table places passes the **card** gate | 0 refused at every tier (`tests/test_card_gate_measured_vram.py::test_every_model_the_published_tier_table_places_is_admitted`) |
| 8 GB list, first rows | `Qwen3.8-27B`, `Qwen3.8-Flash-Next 125B`, `Qwen3.6-35B-A3B`, `Bonsai 2 9B` — the published table's order |
| shuffled store | identical ids at 8 / 16 / 48 GB (`test_the_card_list_does_not_depend_on_the_store_file_order`) |
| red-then-green | reintroducing the `vram_tier` read in `fits()` reds `test_the_gate_never_reads_the_display_label_when_the_store_states_a_measurement` (+ the run-evidence case); restoring the measured gate greens it |
| matrix fixture | `make render-trend-list-matrix` regenerated; `make check-trend-list-matrix` green |

## Decisions taken

- **The README's tier tables are the oracle, not a reimplementation.** The tier-local ranking's
  buzz term cannot be decomposed from the store's single `trend_score`, so llgenie reads the
  published order instead of inventing one.
- **No README beside the store is not an error.** A bare `LLGENIE_REGISTRY_SRC` JSON fixture has
  no `trending-README.md`; the card's list is then the computed store order alone. `data/` is
  untouched by this change (the store lands through the sync PR).
- **The RAM floor moved to the admitting evidence.** Without it the README's own placements were
  refused (`Qwen3.8-27B` states `system_ram_min: 128GB` model-wide while its 4 GB run used 32 GB
  of system RAM).

## Not covered

- #731 (an engine offered whose plan cannot be downloaded) and #228 (the mock (arch, vram, ram)
  grid) — different defects, their own issues.
- A 24 GB placement whose only run states 110 GB of system RAM stays out of a 64 GB host's list:
  the gate is honest, the data is the constraint.
