# 2026-10-30 — issue #1020: the trend-list matrix comparison is routed to the network seam

## What was wrong

`tests/test_trend_list_matrix.py::test_trend_list_matches_the_committed_matrix` compares
`matrix(registry, vram, ram, arch)` against the committed `tests/fixtures/trend-list-matrix.json` for
all 81 cases. The EXPECTED side is committed; the ACTUAL side is not. `matrix()` asks
`_no_fit_reason()` for the smallest download of a model no engine can run, and that reads the LIVE
Hugging Face tree (`gguf_weights() -> _tree()`, `scripts/model_engine_pick.py:760,922,896`);
`mlx_repos()` searches the live Hub too (`:1443`). The test carried no `network` marker, and neither
`tests/fixtures/unit-suite.json` nor `scripts/unit_tests.py` crowded it out, so `make test-unit` —
whose argv ends `-m "not network"` (#1000) — executed 81 live-Hub cases.

Measured on `origin/main@690d8a9f` in `llgenie/test:latest`: 83 passed in **57.11s**, every
non-`(arch,vram,ram)`-shape assertion Hub-dependent.

## What was measured before the change

- `python3 scripts/unit_tests.py list` names `tests/test_trend_list_matrix.py` (line 149); `argv` ends
  `-m not network`. The marker seam existed — only the marks were missing.
- The red the planner reported is at PR #935's head `cee9320a` (run `41115415680`, job
  `124268887802`): the diff is CONTENT, not transport —
  `{'server': 'llama.cpp', 'tps': 6.0, 'variant': 'cuda'} != {'server': 'llama.cpp (PrismML fork)',
  'tps': 128.0, 'variant': 'cpu'}` — so that PR's engine ranking is the thing to fix there. This issue
  is the instrument: a comparison whose answer depends on the Hub's hour does not belong in a gate
  that promises it reads nothing off the network.

## What the change is

- `@pytest.mark.network` on `test_trend_list_matches_the_committed_matrix`, as the LAST decorator
  (directly above `def`), where both marker censuses read it.
- The module docstring states the routing; the marker is NOT quoted as prose anywhere in the file,
  because the #1000 census attributes the marker TEXT to the next `def test_` — a quoted mention would
  claim a mark the file's two hermetic tests do not carry (it did, on the first attempt: the census
  raised `test_trend_list_matrix.py:99: @pytest.mark.network marks nothing`).
- `tests/test_check_model_links.py`: `DATA_PATH_FILES` gains the file and `EXPECTED_NETWORK_TESTS`
  gains its one live test. Placed at the TOP of each structure so the hunks stay away from PR #1074's
  additions (#1059) at the tuple middle and the dict tail; that PR was told on the PR itself.
- No `unit_tests.py`, `tests/fixtures/unit-suite.json` or workflow change: the seam routes it.

## The observation (not the marker text)

```
$ pytest tests/test_trend_list_matrix.py --collect-only -q -m "not network"   # the gate's expression
...::test_the_committed_matrix_is_the_vram_ram_arch_grid
...::test_ram_changes_which_cuda_16gb_model_is_served
2/83 tests collected (81 deselected) in 0.04s

$ pytest tests/test_trend_list_matrix.py --collect-only -q -m network
81/83 tests collected (2 deselected) in 0.03s

$ HTTPS_PROXY=http://127.0.0.1:9 pytest tests/test_trend_list_matrix.py -q -m "not network"
2 passed, 81 deselected in 0.04s        # the hermetic remainder needs no route at all
```

Negative controls, both run in `llgenie/test:latest`:

- marker removed -> `tests/test_check_model_links.py::test_the_network_membership_of_the_hf_data_path_files_is_exact`
  fails with `AssertionError: network-membership drift`; marker restored -> `tests/test_check_model_links.py`
  + `tests/test_network_marker.py` report `14 passed`.
- one committed `tps` perturbed (`179.0 -> 178.0`) -> `[cuda/8/8]` fails on the seam with
  `At index 0 diff: {'model': 'Bonsai 2 9B', 'server': 'llama.cpp', 'tps': 179.0, ...} != {... 'tps': 178.0, ...}`;
  fixture restored byte-identical (`git diff --quiet` then passes).

## Decisions

- **Routing, not a fixture rewrite.** The alternative — making `matrix()` read vendored data so the
  comparison stays in the gate — changes `_no_fit_reason()`/`mlx_repos()` product behaviour (the
  `why` strings) and is the data-path half of #974. Moving the instrument to the seam that owns live
  I/O keeps every assertion.
- **Nothing is lost from `ci-unit`.** The same comparison runs there through
  `make check-trend-list-matrix` (`scripts/trend_list_matrix.py --check`), the guard
  `docs/ARCHITECTURE.md` names for that fixture, so a registry-versus-matrix drift still reds a PR.
- **Per-test marker, not `pytestmark`.** A module-level mark would route the hermetic pins too and
  leave both censuses blind.
