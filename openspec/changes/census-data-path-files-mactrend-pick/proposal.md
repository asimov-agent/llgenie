---
name: census-data-path-files-mactrend-pick
about: the routing census's DATA_PATH_FILES must list tests/test_mac_trend_pick.py so a live Hub fetch in it reds the census
status: active
---

# The routing census covers tests/test_mac_trend_pick.py (issue #1132)

## Proposal

`tests/test_check_model_links.py` holds the routing census of the HF data path (issue #1000): the
`DATA_PATH_FILES` roster names every test file the census scans for `@pytest.mark.network`, and
`EXPECTED_NETWORK_TESTS` pins which tests in those files carry the marker. The census's own test
(`test_the_network_membership_of_the_hf_data_path_files_is_exact`) reads `DATA_PATH_FILES`, so a
file not listed in that roster is invisible to the census — whatever live Hub reach it carries.

`tests/test_mac_trend_pick.py` reaches the live Hub on its seven `@pytest.mark.network` tests
(`_offer` -> `mp.offer` -> the Hub tree, driven by `llgenie --trend`/`--select` on an Apple-Silicon
Mac). It was added for issue #1120, and #1120's marks are what exposed the gap, but the file was never
added to the census roster. The census therefore stayed green over a live Hub fetch, which is the
exact failure mode the census exists to catch.

## Motivation

A roster that answers "is this file routed correctly?" only for the files someone remembered to list
turns a missing entry into silence: the gate is green for every unlisted file, whatever it does. With
`test_mac_trend_pick.py` unlisted, removing a `@pytest.mark.network` marker from it (silently routing
a Hub call back into the hermetic unit gate) reds nothing. Adding it to the roster pins the file: a
marker removed, or a new live Hub fetch left unmarked topology, reds the census naming the file and
the test, exactly as it does for every other routed file.

## Change

- `tests/test_check_model_links.py`: add `"test_mac_trend_pick.py"` to `DATA_PATH_FILES`, and add its
  seven `@pytest.mark.network` test names to `EXPECTED_NETWORK_TESTS`, so the census pins the file's
  routing — a marker removed here reds by file + test instead of silently returning a Hub call to the
  gate. The membership assertion keeps its existing shape: the census asserts every expected mark
  exists and nothing outside the ownership set carries a mark (subset-membership, never a strict
  exact-list equality that reds on the next legitimate addition).
- No code, marker, `unit_tests.py`, roster or workflow change: the file and its marks are already
  correct; this only registers them with the census.
- `agent-wiki/` note + `docs/changes.d/` fragment (the index row lives in the fragment).

## Acceptance

- [ ] `tests/test_check_model_links.py::test_the_network_membership_of_the_hf_data_path_files_is_exact`
      stays GREEN on the corrected tree (the seven marks exist and match).
- [ ] Negative control (sabotage): removing a `@pytest.mark.network` from `tests/test_mac_trend_pick.py`
      reds the census naming the file and test (`network-membership drift`); restoring it returns the
      census to GREEN.
- [ ] `make lint`, `make check-docs`, `make check-wiring`, `make check-pr-hygiene` and
      `make openspec-validate NAME=census-data-path-files-mactrend-pick` exit 0.
- [ ] All tasks below are ticked and the loop gate is green.

## Not covered

- `tests/test_network_marker.py` routing pin deduplication (issue #1131) — filed separately, next in
  the implementer's queue; not folded into this change.
- `check_import_roots` census (issue #1096) — filed separately; not folded into this change.
