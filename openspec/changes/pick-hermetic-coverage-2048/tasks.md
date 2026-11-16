# Tasks: pick-hermetic-coverage-2048

## 1. Accounting test
- [x] 1.1 Add `test_matrix_accounts_every_card_gated_model_offer_or_skip` to `tests/test_pick_matrix.py`: union/disjoint/once/why assertions at 8/16/48 GB against the `trend_list` card-gate enumeration, Hub + engine registry stubbed.

## 2. Band-semantics tests
- [x] 2.1 Add `test_band_narrows_only_the_offered_rows`: default band vs explicit `vram_range=(4, 64)` vs `LLGENIE_VRAM_RANGE="4, 64"` — offered set diff is exactly the off-band model, band skip reason names `VRAM band`, gate enumeration identical, CPU-tier row never band-skipped.
- [x] 2.2 Add `test_skip_reason_shapes_are_distinct` (band / no-engine-image / no-download) and `test_offer_default_view_never_bands` (bonsai shape stays a row in `offer()` without an explicit range).

## 3. Mutation proof (AC2)
- [x] 3.1 Mutate `matrix()` to silently drop the band-skip accounting, confirm the new tests redden locally, revert, confirm green — recorded in the agent-wiki entry.

## 4. Gates
- [x] 4.1 `make test-unit` green with the change; `tests/test_pick_full_registry.py` untouched (git diff proves it).
