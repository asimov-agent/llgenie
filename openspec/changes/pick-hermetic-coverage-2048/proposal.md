# Pick hermetic coverage: offer-or-skip + band semantics in CI-unit

## Why

Issue #2047 fixed the offer-or-skip regression with ONE hermetic band test, but the pick
business logic (#669 offer-or-skip + #227 band-narrowing) still leans on the live-Hub
`tests/test_pick_full_registry.py` (ci-hf-live) for its full-shape coverage. A change that
breaks the invariants in `matrix()`/`offer()` must be red in `make test-unit` (hermetic,
zero network), not only in ci-hf-live minutes-to-hours later.

## What Changes

- `tests/test_pick_matrix.py` gains hermetic full-shape assertions: every card-gated model is
  accounted in `permutations` or `skipped` (disjoint, exactly once, with a reason) across the
  card sizes 8/16/48 GB; the band narrows ONLY the offered matrix rows (off-band-but-fitting →
  skip naming the band; explicit `vram_range` / `LLGENIE_VRAM_RANGE` re-admit them; the
  card-gate enumeration `trend_list` is identical under every band variant); the three skip
  reasons (band / no-engine / no-download) are distinct; `offer()` default never bands.
- `tests/test_pick_full_registry.py` stays unchanged (live-Hub URL proof, #438).
- No change to `scripts/model_engine_pick.py` behaviour, `data/models.json`, or `fits()`.

## Impact

- Affected capability: `pick-vram-ram-matrix`
- Affected code: `tests/test_pick_matrix.py` only (plus docs trio).
