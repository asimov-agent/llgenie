# pick-vram-band-offer-or-skip

## ADDED Requirements

### Requirement: the VRAM band narrows what is offered, never what is accounted

The #669 offer-or-skip invariant survives the #227 VRAM-band scope view: for
every model the card gate `fits(model, gb, ram, arch)` admits, `matrix()` names
it in `permutations` (offered) OR in `skipped` with a reason. A model whose
README display tier (`vram_tier`) falls outside the effective band but that the
measured minimum places on the card must still be accounted — it is skipped
with an explicit band reason, never silently dropped. `offer()` returns a row
for every model `fits()` admits, including a fitting model whose display tier
is out of band.

WHEN `matrix()` runs on a registry whose display tier and measured minimum
disagree across the band edge,

THEN every model `fits()` admits is in `permutations` or `skipped`

AND a fitting out-of-band model appears in `skipped` with a reason naming the
band,

AND no fitting model (in- or out-of-band) is absent from both lists.

WHEN `offer()` builds the list for a host,

THEN it returns a row for every model `fits()` admits for that host, including
an out-of-band-tier model that fits.

#### Scenario: a low-tier model that fits an 8 GB card is skipped-with-reason, never dropped

- **Given** `bonsai-2-2b` (README tier `6GB`, measured `vram_min` `4GB`)
- **And** a card `gb == 8`
- **When** `matrix(registry, 8, ...)` runs
- **Then** `bonsai-2-2b` is in `skipped` with a reason naming the band
- **And** it is also in `tests/test_pick_full_registry.py`'s skipped set for
  the `(vram=8, arch=cuda)` permutation (the #669 assertion)
- **Test:** `tests/test_pick_full_registry.py`; hermetic regression in
  `tests/test_pick_matrix.py::test_matrix_skips_a_fitting_model_outside_the_default_vram_band`

#### Scenario: a fitting out-of-band model is offered by offer()

- **Given** a model `fits()` admits for a card but whose display tier is outside
  the default band
- **When** `offer()` builds that host's rows
- **Then** the model's row is present (with engines if it can be served, else a
  `why`)
- **Test:** `tests/test_trend_list_acceptance.py::test_ac1_rows_are_the_readme_models_that_fit_in_readme_order`
  and `tests/test_trend_pick.py::test_card_16gb_list_on_this_readme`

