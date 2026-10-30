# registry-trend-hermetic

- [x] `tests/test_network_marker.py`: `module_network_reach` / `remote_reach_opens` detect a remote host reached through a helper module, name it, honour the roster's `deselect`, and skip a scope that stubs the transport
- [x] `tests/test_registry_sync_trend.py`: the two live tests carry `@pytest.mark.network`; the vendored twins assert the identical behaviour against `data/models.json` + `data/trending-README.md` (no assertion weakened)
- [x] `tests/test_trend_pick.py`: the second instance the widened scan found (`sr.fetch` of the live contract) is marked, with its hermetic half kept as its own test
- [x] `tests/test_check_model_links.py` census and `pytest.ini` marker description updated; the census fails on an added or removed mark
- [x] Proven both ways: the new scan names 3 violations with the marks stashed and 0 on the fixed tree
- [x] `make test-unit` green **and** green under `docker run --network none` (zero network I/O)
- [x] `agent-wiki/` note + `docs/changes.d/` fragment, `CHANGES.md` re-rendered with `make changes-index`
- [x] `make lint`, `make check-workflows`, `make check-wiring`, `make check-docs`, `make check-pr-hygiene`, `make openspec-tasks-check`, `make openspec-validate NAME=registry-trend-hermetic` all green
