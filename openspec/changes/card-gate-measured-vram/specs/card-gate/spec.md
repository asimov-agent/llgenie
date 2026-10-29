# card-gate spec delta

## ADDED Requirements

### Requirement: A model fits from measured evidence, never from the display label

The picker SHALL admit a model on a card of N GB when the store carries evidence that it runs
at that size, in this order: a measurement whose hardware names a card ≤ N (`ran on`), else a
stated `vram_min` ≤ N, else a stated `weight_gb` ≤ N (the `weights-only` fit). `vram_tier` SHALL
be read only as the last resort, for a row that states neither `vram_min` nor a measurement.
When the store states `system_ram_min`, the host's RAM SHALL also be at least that.

WHEN the store records a run on a 4 GB card and `vram_min` says 12 GB,
THEN a 8 GB card admits the model, and a 4 GB card does too.

WHEN `vram_tier` says 96 GB and a measurement ran on a 4 GB card,
THEN the label never keeps the model out of an 8 GB list.

#### Scenario: a measured run on a smaller card admits the model
Given a model whose declared minimum is above the card but whose store row records a
measurement on a card at or below it,
When `fits(model, card)` runs,
Then it answers yes, because the run is evidence the model runs there.
- **Test:** `tests/test_card_gate_measured_vram.py::test_the_gate_admits_a_model_with_a_measured_run_on_a_smaller_card`

#### Scenario: the display label never decides when the store states a measurement
Given a model that states `vram_min` and has a measured run, and whose `vram_tier` is a much
larger bucket,
When the gate is asked about a card at the measured size,
Then the answer does not change when `vram_tier` is rewritten, in either direction.
- **Test:** `tests/test_card_gate_measured_vram.py::test_the_gate_never_reads_the_display_label_when_the_store_states_a_measurement`

#### Scenario: the weights-only fit admits a model above its declared minimum
Given a model whose `vram_min` is above the card, which states a `weight_gb` at or below it,
and whose smallest measured run is on a bigger card,
When a card of that size is asked,
Then it is admitted as a `weights-only` fit, exactly as the publishing README labels it.
- **Test:** `tests/test_card_gate_measured_vram.py::test_the_weights_only_fit_admits_a_model_above_its_declared_minimum`

#### Scenario: the system-RAM floor still applies
Given a model admitted by the card evidence that states a `system_ram_min` above this host's RAM,
When `fits()` is asked,
Then it answers no.
- **Test:** `tests/test_card_gate_measured_vram.py::test_the_system_ram_floor_still_applies`

### Requirement: Every placement the published tier table makes passes the gate

For every tier the vendored README publishes (`### Up to 8 GB` … `### Up to 48 GB`), every
model that table places SHALL be admitted by `fits(model, tier)`.

WHEN the table places a model at 12 GB,
THEN `fits(model, 12)` answers yes.

#### Scenario: the published tier table is the gate's oracle
Given the vendored store and the vendored README,
When every model the card's `### Up to N GB` table places is asked about card N,
Then none of them is refused.
- **Test:** `tests/test_card_gate_measured_vram.py::test_every_model_the_published_tier_table_places_is_admitted`

### Requirement: The card's list is the published tier-local ranking

`trend_list()` SHALL order the rows it admits by the position the vendored README gives them in
the card's own `### Up to N GB` table (the tier-local trend), and SHALL place the rows that
table does not rank — they still fit, so they stay selectable — after it, in the store's own
trend order. A card above the largest published tier SHALL use that largest tier's ranking.

WHEN a card's tier table ranks two models in an order the global ranking does not,
THEN the card's list follows the tier table.

#### Scenario: the card's list follows the published tier ranking
Given the vendored store and README and an 8 GB card,
When the trend list is built,
Then the rows the `### Up to 8 GB` table ranks appear in that table's order, and that order is
not the store's global "Most loved" order.
- **Test:** `tests/test_card_gate_measured_vram.py::test_the_card_list_follows_the_published_tier_ranking`

### Requirement: The store's file position is not load-bearing

The order of `data/models.json` SHALL NOT decide the card's list. The store's own ranking
(`band → trend score → posts → peak t/s`) SHALL be computed in code, so a store whose rows are
reordered or appended produces the same list, and a card's ranked rows come from the published
tier table rather than from line numbers in the file.

WHEN the store's rows are shuffled,
THEN `trend_list()` returns the identical list of ids.

#### Scenario: a shuffled store produces the same list
Given the vendored store with its `models` list shuffled,
When `trend_list()` is built for a card,
Then the ids are identical to the unshuffled store's.
- **Test:** `tests/test_card_gate_measured_vram.py::test_the_card_list_does_not_depend_on_the_store_file_order`

#### Scenario: the computed key reproduces the published store order
Given the vendored store and the date its ranking was computed for,
When the models are sorted by the computed key,
Then the ids are exactly the committed order — so reading the file's position adds nothing.
- **Test:** `tests/test_card_gate_measured_vram.py::test_the_derived_key_reproduces_the_published_store_order`
