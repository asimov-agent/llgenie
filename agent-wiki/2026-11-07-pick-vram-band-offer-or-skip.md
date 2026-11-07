# pick VRAM-band offer-or-skip invariant (issue #2047) — 2026-11-07

**Implements:** issue #2047 — a main-red regression introduced by the #1969
VRAM-range scope filter (issue #227): `scope_models` narrowed the interactive
view by the README display tier BEFORE the card gate `fits()` (issue #669), so a
model that fits the card but whose tier falls outside the default 8–48 GB band
appeared in `matrix()`/`offer()` neither OFFERED nor in `skipped` — silently
absent. Main was red on ci-hf-live (run `42404853776`, 453 failed) at every tip
since the `6921b35f` merge.

## What changed

- **`scripts/model_engine_pick.py`**
  - `matrix()` now enumerates the FULL fitting registry (the #669 card gate) and
    keeps out-of-band-but-fitting models in `skipped` with an explicit reason
    ("outside the `<lo>–<hi>` GB VRAM band, tier `<T>`") — the band narrows which
    models are OFFERED, never which models are *accounted*. A fitting model is
    never silently absent.
  - `offer()` returns a row for every model `fits()` admits, including a fitting
    model whose display tier is out of the default band (a row it cannot serve
    still carries a `why`). The band is respected only when a caller EXPLICITLY
    passes `vram_range`; the default (None) is the full fitting list the trend
    tests assert.
- **`tests/test_pick_matrix.py`** — hermetic regression
  `test_matrix_skips_a_fitting_model_outside_the_default_vram_band` (stubbed Hub
  tree + engine registry, no network): asserts an off-band-but-fitting model is
  skipped-with-reason in `matrix()`, and that the reason is DISTINCT from the
  no-download reason. Runs in `make test-unit` (CI-unit).

## Verified

- `make test-unit` hermetic green at the fix head: `tests/test_pick_matrix.py`
  + the pick/trend files + `test_vram_scope_filter.py` all pass (145 passed,
  including the new regression).
- The live-Hub duplicate (`tests/test_pick_full_registry.py`, `@pytest.mark.network`,
  ci-hf-live) is unchanged — it still proves the offered URLs are real
  (#438/#1000); the two seams stay complementary.

## Decisions

The scope band narrows the OFFERED/permutation set; it never silently absent a
model the card gate fits (issue #669 wins over the #227 view narrowing). A later
follow-up (#2048) extends the same hermetic-in-CI-unit coverage to the whole
pick-set business logic, keeping the live-Hub set as-is.

