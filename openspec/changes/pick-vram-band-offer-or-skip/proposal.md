# pick-vram-band-offer-or-skip — proposal

Issue: [#2047](https://github.com/asimov-agent/llgenie/issues/2047)

## Why

The #1969 VRAM-range scope view (issue #227) made `offer()`/`matrix()` band-scope
the registry by the README display tier **before** the card gate `fits()`
(issue #669) enumerates the offered/skipped sets. That broke the #669 pick
invariant ("a model that fits a card is offered or skipped-with-a-reason,
never silently absent"): a model whose display tier is out of the 8–48 GB band
but that the measured minimum places on the card is dropped *before* `matrix()`
builds its `skipped` list. Deterministic, non-flaky: `bonsai-2-2b` (tier 6 GB,
`vram_min` 4 GB) fits an 8 GB card but is neither offered nor in `skipped`.
Main is red on ci-hf-live (run `42404853776`, 453 failed in the pick set) at
every tip since the `6921b35f` merge.

## What Changes

- **`matrix()`** (`scripts/model_engine_pick.py`): enumerate the full
  fitting set (the card gate #669), then keep out-of-band-but-fitting models
  in `skipped` with an explicit reason ("outside the `<lo>–<hi>` GB VRAM
  band, tier `<T>`") — the band narrows which models are OFFERED, never which
  models are *accounted*. A fitting model is never silently absent.
- **`offer()`**: return rows for every model the card gate fits, including a
  fitting model whose display tier falls outside the default band. The
  interactive view narrows the offered/permutation set, not the fitted-row set
  (a row the host cannot serve already carries a `why`).
- A regression test asserts the contract explicitly: a fitting model outside
  the default band (e.g. `bonsai-2-2b`) is skipped-with-reason in `matrix()`,
  never dropped.

## Not covered

- Changing `data/models.json` (kept verbatim, per #227/#2047 out of scope).
- Weakening the card gate `fits()` / the measured-VRAM rule (issue #669).
- Changing the pure `scope_models()` filter or `trend_list()` band behaviour —
  those keep the #227 semantics; this change fixes the CONSUMERS so the
  offer-or-skip invariant survives the band.

Refs: #2047 (this issue), #227 (the scope view), #669 (offer-or-skip invariant),
#1969 (the merge that regressed main).

