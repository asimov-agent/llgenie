# trend-list-matrix-network-seam

## ADDED Requirements

### Requirement: The committed-matrix comparison runs only on the network seam

`tests/test_trend_list_matrix.py::test_trend_list_matches_the_committed_matrix` SHALL carry the
`network` marker, because its actual side calls `matrix()`, which sizes a non-fitting model from the
live Hugging Face tree (`_no_fit_reason() -> gguf_weights() -> _tree()`) and searches the Hub for MLX
repositories (`mlx_repos()`). The hermetic unit gate (`make test-unit`, `-m "not network"`) SHALL
collect zero nodes from it, and the network seam (`make test-unit-network`, `-m network`) SHALL own
all 81 of its parameterised nodes.

WHEN the hermetic gate's selection is computed
THEN no node of `test_trend_list_matches_the_committed_matrix` SHALL be collected, and the network
seam SHALL collect every one of them.

#### Scenario: the gate collects no node from the live comparison

Given the gate's own expression `-m "not network"` over the whole discovered selection
When  the live file is collected
Then  only its two fixture-only pins are collected — the 81 parameter cases are deselected.

- **Test:** `tests/test_network_marker.py::test_the_unit_gate_executes_zero_network_marked_tests`

#### Scenario: the network seam owns the marks

Given the file with the marker on its live test
When  `pytest --collect-only -m network` runs over the gate's selection
Then  every marked node is collected, so the mark is membership and not decoration.

- **Test:** `tests/test_network_marker.py::test_the_network_pipeline_owns_the_marks`

### Requirement: The routing decision is pinned, in both directions

The #1000 routing census SHALL name `test_trend_list_matrix.py` in `DATA_PATH_FILES` and
`test_trend_list_matches_the_committed_matrix` in `EXPECTED_NETWORK_TESTS`, so a removed marker is a
named red and an unlisted real-Hub file is impossible.

WHEN the census reads the data-path files
THEN the marks found SHALL equal the expected map exactly, naming the file and the test on any drift.

#### Scenario: a removed marker reds the census

Given the marker removed from the live test and the census unchanged
When  `tests/test_check_model_links.py::test_the_network_membership_of_the_hf_data_path_files_is_exact`
      runs
Then  it fails with `network-membership drift`, naming `test_trend_list_matrix.py`.

- **Test:** `tests/test_check_model_links.py::test_the_network_membership_of_the_hf_data_path_files_is_exact`

### Requirement: The live comparison still catches a matrix regression

Routing a test to the seam SHALL NOT weaken it: on the network seam the comparison SHALL still fail,
naming the model and both values, when the committed matrix and `matrix()` disagree.

WHEN a committed row is perturbed
THEN the corresponding case fails with the model name and the two differing rows.

#### Scenario: a perturbed fixture reds the assertion on the seam

Given `tests/fixtures/trend-list-matrix.json` with one `tps` value changed for the `cuda/8/8` case
When  `test_trend_list_matches_the_committed_matrix[cuda/8/8]` runs under `-m network`
Then  it fails at the row comparison, naming the model and both tps figures.

- **Test:** `tests/test_trend_list_matrix.py::test_trend_list_matches_the_committed_matrix` (network
  seam; run by `make test-unit-network`)

#### Scenario: the hermetic pins stay in the gate

Given the committed fixture and the vendored registry
When  `make test-unit` runs
Then  the parameter grid + stamp pin and the RAM ladder still execute, so the fixture's shape is
      still gated hermetically.

- **Test:** `tests/test_trend_list_matrix.py::test_the_committed_matrix_is_the_vram_ram_arch_grid` and
  `tests/test_trend_list_matrix.py::test_ram_changes_which_cuda_16gb_model_is_served`
