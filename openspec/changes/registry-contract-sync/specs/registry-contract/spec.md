# registry-contract

## ADDED Requirements

### Requirement: A stated footprint is read, and the run's own value wins

llgenie SHALL read the model contract's stated footprint (`weight_gb`, `context_tokens`,
`system_ram_min`, `storage_offload`, `engine_min_version`) when it decides what this host can run, and
SHALL prefer the value stated on an individual `engines[]` measurement over the model-level value for
that engine. A field the store does not state SHALL be treated as absent — never invented, and never
defaulted to a number.

WHEN a model and one of its measurements both state a footprint
THEN the measurement's value SHALL be used for that engine, and the model's SHALL fill only the fields
the measurement does not state.

#### Scenario: the measurement's own footprint wins

Given a model stating `weight_gb` 9.2GB and a `llama.cpp` measurement of it stating 5.95GB
When  the footprint of that measurement is read
Then  the measurement's 5.95GB is returned, and the model's 9.2GB is not

- **Test:** `tests/test_registry_footprint.py::test_the_measurement_footprint_wins_over_the_model_one`

#### Scenario: an absent field stays absent

Given a model that states no `engine_min_version`
When  its footprint is read
Then  the returned mapping has no `engine_min_version` key at all

- **Test:** `tests/test_registry_footprint.py::test_the_measurement_footprint_wins_over_the_model_one`

#### Scenario: the stated sizes and contexts are parsed, not guessed

Given the stored spellings `5.95GB Q4_K_M`, `800MB`, `640GB NVMe, experts on SSD`, `128K` and `1M`
When  they are read as a size or as a token window
Then  they yield 5.95 GB, 0.78 GB, 640 GB, 131072 and 1048576, and a value with no number yields None

- **Test:** `tests/test_registry_footprint.py::test_a_stated_size_is_read_as_gb_and_never_invented`
  and `tests/test_registry_footprint.py::test_a_stated_context_is_read_in_tokens`

### Requirement: A stated RAM floor and weight budget decide the fit

A model whose stated `system_ram_min` exceeds this host's RAM SHALL NOT be offered as fitting, and the
reason a model does not fit SHALL cite the stated RAM floor or the stated weight budget before any
estimate derived from a download.

WHEN a model states a `system_ram_min` above this host's RAM
THEN the trend list SHALL exclude it, and the no-fit reason SHALL name the stated floor and this
host's RAM.

#### Scenario: the RAM floor excludes a model the card alone would fit

Given a 24GB-tier model stating `system_ram_min` 64GB and a 24GB card
When  the fit is evaluated on a host with 32GB of RAM and on one with 128GB
Then  it is False on the 32GB host and True on the 128GB host

- **Test:** `tests/test_registry_footprint.py::test_a_stated_system_ram_floor_excludes_the_model`

#### Scenario: a store that states no RAM behaves exactly as before

Given a model with no footprint fields
When  the fit is evaluated for a card that fits and for one that does not
Then  only the VRAM column decides, as before

- **Test:** `tests/test_registry_footprint.py::test_no_stated_ram_keeps_the_previous_behaviour`

#### Scenario: the printed list honours the RAM floor

Given a registry whose only model states `system_ram_min` 64GB
When  the trend list is built for a 32GB host and for a 128GB host
Then  the model is absent on the 32GB host and present on the 128GB one

- **Test:** `tests/test_registry_footprint.py::test_the_trend_list_drops_a_model_whose_stated_ram_is_above_this_host`

#### Scenario: the engine row carries the run's footprint

Given a `llama.cpp` measurement stating weight, context and a required engine build
When  the engines are ranked for that card
Then  the `llama.cpp` row's footprint carries those stated values

- **Test:** `tests/test_registry_footprint.py::test_an_engine_row_carries_the_measurements_own_footprint`

#### Scenario: the no-fit reason cites the store before a download estimate

Given a model stating `system_ram_min` 64GB and no readable Hub file list
When  the no-fit reason is built for a 32GB host
Then  the reason names the 64GB floor and this host's 32GB, and does not claim a GGUF size

- **Test:** `tests/test_registry_footprint.py::test_the_no_fit_reason_names_the_stated_ram_before_any_file_size`

### Requirement: The stated footprint is additive only

The registry's additive-only guard SHALL treat `weight_gb`, `context_tokens` and `system_ram_min` as
grow-only, both on the model and inside a measurement, so a sync that shrinks what a run needs is a
finding — while a grown value, a restated one, or a newly stated field is not.

WHEN a sync lowers a stated footprint
THEN `check-registry-keys` SHALL report it and exit non-zero, naming the model and the measurement
where it applies.

#### Scenario: a lowered model-level footprint is a loss

Given a registry stating `weight_gb` 9.2GB, `context_tokens` 131072 and `system_ram_min` 32GB
When  a sync restates them as 5.95GB, 32768 and 16GB
Then  the guard reports each one as lowered

- **Test:** `tests/test_registry_footprint.py::test_a_lowered_stated_footprint_is_a_loss`

#### Scenario: growing or restating a footprint is not a loss

Given a registry stating `weight_gb` 5.95GB and `context_tokens` 131072
When  a sync grows the weight, restates the context with a unit word and adds `system_ram_min`
Then  the guard reports nothing

- **Test:** `tests/test_registry_footprint.py::test_a_grown_or_restated_footprint_is_not_a_loss`

#### Scenario: a measurement's own footprint cannot silently disappear

Given a measurement stating `weight_gb` 5.95GB
When  a sync drops that field from the same `(engine, hardware)` measurement
Then  the guard reports the measurement's `weight_gb` as lowered

- **Test:** `tests/test_registry_footprint.py::test_a_measurement_footprint_that_disappears_is_a_loss`
