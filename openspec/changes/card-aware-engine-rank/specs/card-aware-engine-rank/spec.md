# card-aware-engine-rank

## ADDED Requirements

### Requirement: A measurement is compared to this host's card, not just its backend

`rank_engines` MUST rank a model's engines for this host by the evidence that
describes THIS card. A backend class (CUDA vs ROCm) is not a card class: a
figure measured on a card bigger than this host's predicts nothing for this
host, so it MUST NOT be presented as a fit (`same_hw`) nor rank above a figure
that was proven on this card's class or smaller. The card a measurement ran on
MUST come from the registry's own `hardware` string, and a datacenter part
(H100/A100/B300/MI300/GB200 …) MUST never count as a fit — both exactly as the
trending-local-llms README defines them.

WHEN a model with measurements from several cards is ranked for a host with a
known card, THEN the engine whose figure was measured on this host's card class
or smaller MUST come first, and a same-backend figure from a bigger card MUST be
labelled with that card and rank below every proven figure.

#### Scenario: a figure proven on this card class outranks a faster figure from a bigger card

- **Given** one engine with two CUDA figures: 140 t/s on an `RTX 3090 24GB` and 97 t/s on a `RTX 5070 12GB`
- **When** the model is ranked for a 16 GB CUDA host
- **Then** the 97 t/s figure is the row kept for that engine, ranked 0 with `same_hw` true
- **And** the 140 t/s figure is not the recommendation (it describes a bigger card)
- **Test:** `tests/test_card_aware_rank.py::test_a_figure_proven_on_this_card_class_ranks_first`

#### Scenario: a same-backend figure from a bigger card is labelled and down-ranked

- **Given** a model whose only CUDA figure is 300 t/s on `2x RTX 4090` (48 GB)
- **When** the model is ranked for a 16 GB CUDA host
- **Then** that engine is ranked 1 with `card_class` `bigger`, `card_gb` 48 and `same_hw` false
- **And** it still ranks above a figure from another backend
- **Test:** `tests/test_card_aware_rank.py::test_a_figure_from_a_bigger_card_is_labelled_and_down_ranked`

#### Scenario: the hardware string decides the card, as upstream reads it

- **Given** the hardware strings the registry actually carries
- **When** `measurement_card_gb` reads each of them
- **Then** an explicit `NN GB` wins over a card model, a known card resolves to its VRAM, `Nx` multiplies, and a host that names no card yields None
- **And** `RTX 4090 Laptop` resolves to 16 GB, not 24
- **Test:** `tests/test_card_aware_rank.py::test_measurement_card_gb_reads_the_hardware_string`

#### Scenario: no card class on this host keeps the backend ranking

- **Given** an Apple-Silicon or CPU host, or a card that could not be detected (no card size known)
- **When** the model is ranked
- **Then** the backend rule alone orders the ranks — the same figures that ranked first before this change still rank first
- **Test:** `tests/test_card_aware_rank.py::test_no_card_class_keeps_the_backend_ranking`, `tests/test_trend_pick.py::test_engine_order_proven_then_other_hw_then_supported_only`

### Requirement: A datacenter figure is never a fit for a card

A measurement whose hardware names a datacenter part MUST rank below every
consumer/workstation figure, whatever backend ran it, and MUST NOT be `same_hw`.
A datacenter number that no reader can reproduce on their own card MUST NOT be
the engine llgenie offers by default.

WHEN a model's fastest figure comes from a datacenter part, THEN the default
engine MUST be the best consumer figure instead.

#### Scenario: a 21 000 t/s B300 figure does not top a 16 GB card

- **Given** a model with a 21 000 t/s figure on `single NVIDIA B300 GPU (datacenter)` and a 40 t/s figure on an `RTX 3060`
- **When** the model is ranked for a 16 GB CUDA host
- **Then** the RTX 3060 figure is `same_hw` and ranks first
- **And** the B300 row is ranked 4 with `card_class` `datacenter`, below even a consumer ROCm figure
- **Test:** `tests/test_card_aware_rank.py::test_a_datacenter_figure_ranks_below_every_consumer_figure`, `tests/test_card_aware_rank.py::test_datacenter_hardware_names_never_count`

#### Scenario: the real registry's datacenter rows are out of the recommendation

- **Given** the vendored registry at 2026-10-13 with its `single NVIDIA B300 GPU (datacenter)` and `DGX Spark` rows
- **When** a model carrying them is ranked for a 16 GB CUDA host
- **Then** no `same_hw` row names a datacenter part
- **Test:** `tests/test_card_aware_rank.py::test_a_datacenter_figure_ranks_below_every_consumer_figure`

### Requirement: The t/s text says where the figure came from

Every t/s a user reads MUST come from ONE rule (`model_engine_pick.tps_label`),
so the printed list and the tests that lock it cannot disagree: a figure proven
on this card class shows bare, a same-backend figure from a bigger card names
that card, a same-backend figure from hardware that names no card says so, a
datacenter figure says datacenter, another backend shows its backend, and an
engine with no figure shows `supported`.

WHEN the list, the engine menu or the pick summary prints a row, THEN the text
MUST be `tps_label(row)`'s output.

#### Scenario: the label names the card a figure was measured on

- **Given** rows ranked 0 (proven), 1 (bigger card), 2 (no card named), 4 (datacenter), 3 (another backend) and 5 (no figure)
- **When** each row is labelled
- **Then** the labels are `124 t/s`, `300 t/s (CUDA, 48 GB card)`, `67 t/s (CUDA, card unknown)`, `21000 t/s (CUDA, datacenter)`, `96 t/s (ROCm)`, `supported`
- **Test:** `tests/test_card_aware_rank.py::test_tps_label_says_where_the_figure_came_from`

#### Scenario: the printed trend list carries the same label

- **Given** the rows llgenie computed for a host
- **When** `llgenie --trend` prints them
- **Then** each row's line contains `model_engine_pick.tps_label(engines[0])`
- **Test:** `tests/test_trend_list_acceptance.py::test_ac2_ac7_ac8_printed_list_numbering_labels_and_header`

### Requirement: The card-aware ranking reaches the pick's default

The card size a caller knows MUST reach `rank_engines` through every path that
chooses an engine for this host — `rank_models`, `recommend` and `matrix` — so
the row's server (and therefore the download `--auto` takes) is the card-aware
choice, not the raw-t/s one.

WHEN the trend list or the `(arch, vram, ram)` matrix is built, THEN each row's
first engine MUST be the one `rank_engines(..., gb=<that vram>)` ranks first.

#### Scenario: the trend list's server changes with the card size

- **Given** the vendored registry
- **When** the trend list is built for a 16 GB CUDA card and for a 48 GB one
- **Then** each row's top engine has `card_class` set and is the same engine `rank_engines(m, "cuda", gb=<vram>)` returns first
- **And** a row whose best figure is on a bigger card than 16 GB is not served as `same_hw` there
- **Test:** `tests/test_card_aware_rank.py::test_the_trend_list_server_is_card_aware`

#### Scenario: the committed matrix fixture is the card-aware grid

- **Given** the committed `tests/fixtures/trend-list-matrix.json`
- **When** `make check-trend-list-matrix` recomputes the grid
- **Then** it matches, so a change to the ranking is visible as the fixture diff
- **Test:** CI job `ci-unit` -> `make check-trend-list-matrix`

### Requirement: The #225 acceptance case names a comparable card

Given the vendored registry at 2026-10-13, the top engine for
`qwen3.8-flash-next-125b` on a 16 GB CUDA card MUST be justified by a figure
measured on a comparable card, and the out-of-class figure MUST be labelled and
down-ranked — the acceptance criterion of issue #225.

WHEN that model is ranked for a 16 GB CUDA card, THEN the top row's figure was
measured on a card no bigger than 16 GB and the DGX Spark / 24 GB figures are
labelled and below it.

#### Scenario: Strata's 12 GB figure leads on a 16 GB card

- **Given** `qwen3.8-flash-next-125b` in the vendored registry (Strata 140 t/s on `RTX 3090 24GB`, Strata 97.3 t/s on `RTX 5070 12GB`, TensorFold 67 t/s on `DGX Spark`)
- **When** the model is ranked for a 16 GB CUDA card
- **Then** the first row's figure is `97.3` t/s, `card_gb` 12, `same_hw` true
- **And** the 24 GB and DGX Spark rows rank below it, labelled by card or by `card unknown`
- **And** no engine is addressed by a fixed index — the assertions read rows by engine id
- **Test:** `tests/test_card_aware_rank.py::test_225_acceptance_strata_on_a_16gb_card`
