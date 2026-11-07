# pick-vram-band-offer-or-skip — Tasks

Issue: [#2047](https://github.com/asimov-agent/llgenie/issues/2047)

- [x] 1. `matrix()` in `scripts/model_engine_pick.py`: enumerate the full fitting registry (card gate #669) and keep out-of-band-but-fitting models in `skipped` with an explicit band reason — the band narrows what is OFFERED, never what is accounted. Verified: `tests/test_pick_full_registry.py` (all `_PERMS`) green; regression test below.
- [x] 2. `offer()` returns rows for every model the card gate fits, including a fitting model whose display tier is outside the default band. Verified: `tests/test_trend_list_acceptance.py` AC1 / `tests/test_trend_pick.py` card-list assertions green at the fix head.
- [x] 3. Regression test: a fitting model outside the default band (e.g. `bonsai-2-2b`) is skipped-with-reason in `matrix()`, never dropped. Verified: `make test-unit` includes the new assertion and it passes hermetically and in the network set.
- [x] 4. Gates: `make openspec-validate NAME=pick-vram-band-offer-or-skip` exits 0, all tasks ticked; `make test-unit` (hermetic) green; `make test-unit-network` (the pick set) green at the fix head.

