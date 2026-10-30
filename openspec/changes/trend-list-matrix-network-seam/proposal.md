# The trend-list matrix comparison moves to the network seam

## Why

`tests/test_trend_list_matrix.py::test_trend_list_matches_the_committed_matrix` compares
`matrix(registry, vram, ram, arch)` against `tests/fixtures/trend-list-matrix.json` for all 81
`(arch, vram, ram)` cases. Its expected side is committed, but its ACTUAL side is not a pure function
of the vendored registry: for every model no engine can run, `matrix()` asks `_no_fit_reason()`, which
sizes the smallest download from the LIVE Hugging Face tree (`gguf_weights() -> _tree()`,
`scripts/model_engine_pick.py:760,922,896`), and `mlx_repos()` searches the live Hub
(`scripts/model_engine_pick.py:1443`). The test carried no `network` marker and neither
`tests/fixtures/unit-suite.json` nor `scripts/unit_tests.py` crowded it out, so `make test-unit` —
whose argv ends `-m "not network"` (issue #1000) — executed 81 live-Hub cases.

Measured on `origin/main@690d8a9f` in `llgenie/test:latest`: the file runs green but takes
**57.11s** for 83 tests, and 81 of those nodes are Hub-dependent. Measured on PR #935's head
`cee9320a`, run `41115415680` job `124268887802`: `linux / unit` red with
`test_trend_list_matches_the_committed_matrix[cuda/8/{8,32,60,64}]`, each diffing an engine row
(`'server': 'llama.cpp', 'tps': 6.0, 'variant': 'cuda'` against the committed
`'llama.cpp (PrismML fork)', 128.0, 'cpu'`). The content half of that mismatch is #935's own, but the
instrument that reports it belongs to the live seam, not to the gate that promises no Hub calls: a
hermetic gate whose verdict depends on the Hub's answer of the hour reds for reasons unrelated to the
diff, and teaches people to ignore a red `test-unit`.

## What Changes

- **`tests/test_trend_list_matrix.py`** — `test_trend_list_matches_the_committed_matrix` carries
  `@pytest.mark.network` as the LAST decorator (directly above `def`, where both marker censuses read
  it). Its module docstring states the routing and why `matrix()` is not hermetic. The file's two
  hermetic pins — `test_the_committed_matrix_is_the_vram_ram_arch_grid` (the parameter grid + the
  registry stamp) and `test_ram_changes_which_cuda_16gb_model_is_served` (the RAM ladder, read from
  the committed fixture) — stay unmarked and stay in the gate.
- **`tests/test_check_model_links.py`** — the #1000 routing census gains `test_trend_list_matrix.py`
  in `DATA_PATH_FILES` and its one live test in `EXPECTED_NETWORK_TESTS`, so deleting the marker is a
  named red (`network-membership drift`) instead of a silent return of Hub I/O to the gate.
- **No `scripts/unit_tests.py`, `tests/fixtures/unit-suite.json` or workflow change** — the file
  stays discovered and the existing seam routes it: `make test-unit` runs `-m "not network"`,
  `make test-unit-network` (the admitted `ci-hf-live` pipeline) runs `-m network`.
- **No assertion is deleted.** The same comparison also runs inside `ci-unit` through
  `make check-trend-list-matrix` (`scripts/trend_list_matrix.py --check`), which `docs/ARCHITECTURE.md`
  names as the fixture's guard, so drift between the vendored registry and the committed matrix is
  still caught on every PR.

## Out of scope

- `scripts/model_engine_pick.py` still resolves `_no_fit_reason()` and `mlx_repos()` against the live
  Hub; making `matrix()` itself hermetic (so the comparison could stay in the gate) is the data-path
  half of #974, a product change with its own compatibility surface.
- `tests/test_registry_sync_trend.py` (#1067) and `tests/test_pick_full_registry.py` (#1059) — separate
  files, separate lanes.
