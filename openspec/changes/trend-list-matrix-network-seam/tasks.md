# Tasks — trend-list-matrix-network-seam (issue #1020)

- [x] 1. OpenSpec change: `proposal.md`, `specs/trend-list-matrix-network-seam/spec.md`, this checklist
- [x] 2. `tests/test_trend_list_matrix.py`: `@pytest.mark.network` as the last decorator on `test_trend_list_matches_the_committed_matrix`; module docstring states the routing (`matrix()` is not hermetic)
- [x] 3. `tests/test_check_model_links.py`: the #1000 census names the file in `DATA_PATH_FILES` and the test in `EXPECTED_NETWORK_TESTS`
- [x] 4. Observation: the gate's expression collects 2 of 83 nodes from the file (`2/83 collected, 81 deselected`), `-m network` collects `81/83`; the 2 hermetic pins pass in 0.04s with an unroutable proxy
- [x] 5. Negative control: removing the marker reds the census with `network-membership drift`; perturbing one committed `tps` reds `[cuda/8/8]` on the seam naming the model and both values
- [x] 6. `agent-wiki/2026-10-30-trend-list-matrix-network-seam.md` note + `docs/changes.d/` fragment, `CHANGES.md` re-rendered by `make changes-index`
- [ ] 7. Verified: `make test-unit`, `make check-docs`, `make check-wiring`, `make lint`, `make openspec-validate NAME=trend-list-matrix-network-seam` all exit 0
