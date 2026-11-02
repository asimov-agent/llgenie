# 2026-11-02 — issue #1132: the routing census covers tests/test_mac_trend_pick.py

## What was wrong

`tests/test_check_model_links.py` holds the routing census of the HF data path (issue #1000):
`DATA_PATH_FILES` is the roster of test files the census scans for `@pytest.mark.network`, and
`EXPECTED_NETWORK_TESTS` is the ownership set. The census's membership test
(`test_the_network_membership_of_the_hf_data_path_files_is_exact`) iterates `DATA_PATH_FILES` — so a
file never listed in that roster is invisible to the census, whatever live Hub reach it carries.

`tests/test_mac_trend_pick.py` was added for issue #1120 (its seven `@pytest.mark.network` tests
reach the live Hub through `_offer` → `mp.offer` → the Hub tree, driven by `llgenie --trend`/`--select`
on a Mac), but was never added to the census roster. The census stayed green over exactly the live
Hub fetch it exists to catch: removing a marker from that file would silently route a Hub call back
into the hermetic unit gate and red nothing.

## The change

- `tests/test_check_model_links.py`: add `"test_mac_trend_pick.py"` to `DATA_PATH_FILES` and its
  seven `@pytest.mark.network` tests to `EXPECTED_NETWORK_TESTS`, so the census pins the file's
  routing. The membership assertion keeps its subset-membership shape (every expected mark present,
  nothing unlisted marked — never an exact-list equality that reds on the next legitimate addition).

Measured at `origin/main@27e2f4fa`: the file was absent from the census (grep found no
`test_mac_trend_pick` in `tests/test_check_model_links.py`), and the seven marks exist in the file.

## The sabotage loop (proved the gate now covers the file)

1. Corrected tree, census test runs GREEN.
2. Removed one `@pytest.mark.network` (`test_trend_on_a_48gb_mac_is_the_readme_list_with_metal_engines`)
   → census RED, `network-membership drift`, diff names `test_mac_trend_pick.py` and the lost test.
3. Restored the mark → census GREEN again.

## Decisions

- Out of scope (filed separately, next in the implementer's queue): `tests/test_network_marker.py`
  routing-pin deduplication (#1131) and `check_import_roots` (#1096). Not folded into this change.
- No code, marker, `unit_tests.py`, roster or workflow change — only registering an existing file
  and its correct marks with the census.

Related: issue #1132, PR #<PR>.
