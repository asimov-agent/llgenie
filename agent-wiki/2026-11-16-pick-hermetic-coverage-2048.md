# Pick hermetic coverage: offer-or-skip + band semantics in CI-unit (issue #2048)

Closes the #2048 gap: the #669 offer-or-skip invariant and the #227 band-narrowing
semantics now have hermetic full-shape assertions in `tests/test_pick_matrix.py`, so a
mutation to `matrix()`/`offer()` reddens `make test-unit` instead of only ci-hf-live.

## What was verified

- Four new tests (11 total in the module, all hermetic — stubbed Hub tree, real local
  `image_ids.json`, no network):
  - `test_matrix_accounts_every_card_gated_model_offer_or_skip`: at 8/16/48 GB the union
    of `permutations` ids and `skipped` ids equals the `trend_list(registry, gb, ram)` card
    gate exactly; disjoint, no model skipped twice, every skip row carries a reason.
  - `test_band_narrows_only_the_offered_rows`: default band vs `vram_range=(4, 64)` vs
    `LLGENIE_VRAM_RANGE="4, 64"` share one gate enumeration; the widened views offer exactly
    the off-band-but-fitting model; default skip names `VRAM band`; CPU-tier row band-immune.
  - `test_skip_reason_shapes_are_distinct`: band / no-engine-image / no-download reasons
    stay three distinct homes.
  - `test_offer_default_view_never_bands`: `offer()`'s default keeps the bonsai shape as a
    row (plans or `why`); an explicit `vram_range` filters only the view.
- Mutation proof (AC2): replacing the band-skip accounting in `matrix()` with a silent
  `continue` (the exact #2047 regression shape) reddened 3 tests in the module
  (`test_matrix_skips_a_fitting_model_outside_the_default_vram_band`,
  `test_band_narrows_only_the_offered_rows`, `test_skip_reason_shapes_are_distinct`);
  `git checkout -- scripts/model_engine_pick.py` restored 11/11 green.
- `tests/test_pick_full_registry.py` untouched (`git diff --stat` empty) — it stays the
  live-Hub URL proof (ci-hf-live, #438).
- `scripts/model_engine_pick.py` behaviour unchanged: the PR touches tests + docs only.

## Key decisions

- Engine registry is NOT stubbed (real `image_ids.json` is a hermetic local file); the
  earlier `engine_ids = lambda: IDS` set-stub only fed the no-engine path — the mlx-shape
  model needs `engines: []` to reach the engine-home skip.
- Capability delta lands on the existing `pick-vram-ram-matrix` spec (ADDED requirements),
  not a new capability.

## Current status

OpenSpec `pick-hermetic-coverage-2048` validated; branch `feat/pick-hermetic-coverage-2048`
off `origin/main`; full `make test-unit` green before push (see tasks 4.1).
