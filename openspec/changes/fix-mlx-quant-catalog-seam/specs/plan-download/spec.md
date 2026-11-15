## ADDED Requirements

### Requirement: A catalogued mlx/safetensors pair resolves from the committed quant table

When `plan_download` is asked for the `mlx-safetensors` or `safetensors` format of a
(model, engine) pair the committed HF class table (`data/trending-quant-catalog.json`)
lists, it SHALL serve the largest budget-fitting snapshot the table records — its
`{repo, revision, path, files, size}` as a real resolvable plan — and SHALL NOT re-query
the live Hub to learn what the engine can load. An upstream repo re-push that a live
re-read would no longer fit the card budget cannot flip the pick. A pair the table does
not list SHALL still resolve live. (`scripts/model_engine_pick.py` `plan_download`, issue
#2719)

#### Scenario: The table's size wins over a diverged live repo

- **WHEN** a catalogue pair's live repo has been re-pushed so large that a live read no
  longer fits the card budget, but the committed table still lists a budget-fitting size
- **THEN** `plan_download` returns the table's plan (its repo, size and files), not the
  re-pushed live size

- **Test:** `tests/test_pick_quant_catalog.py::test_catalogued_mlx_model_resolves_from_table_when_live_diverges`

#### Scenario: A catalogue pair with no fitting table plan refuses

- **WHEN** the committed table lists the pair but no snapshot it records fits the card budget
- **THEN** `plan_download` returns None — it never falls back to a live repo the table did
  not certify

- **Test:** `tests/test_pick_quant_catalog.py::test_catalogued_mlx_model_with_only_oversized_table_plan_refuses`

#### Scenario: An unlisted pair still resolves live

- **WHEN** the (model, engine) pair is not in the committed table
- **THEN** `plan_download` resolves live as before — the documented fallback is kept

- **Test:** `tests/test_pick_quant_catalog.py::test_uncatalogued_model_falls_back_to_live`

#### Scenario: plan_download and matrix() agree for the same catalogue cell

- **WHEN** a model+card has a catalogue mlx cell that fits the budget
- **THEN** `matrix()`'s `engine_supported_quants` and `plan_download` serve the same plan,
  so `llgenie --pick` delivers what the matrix offers

- **Test:** `make test-unit-network` (`tests/test_pick_full_registry.py::test_pick_matrix_llgenie_cli_agrees_with_business_logic`, the ci-hf-live lane)
