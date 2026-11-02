# Tasks — census-data-path-files-mactrend-pick

- [x] 1. `openspec/changes/census-data-path-files-mactrend-pick` — proposal + `specs/data-path-files-census/spec.md` (G/W/T) + this checklist, written before any code (done pre-implementation)
- [x] 2. `tests/test_check_model_links.py` — add `"test_mac_trend_pick.py"` to `DATA_PATH_FILES` and its seven `@pytest.mark.network` test names to `EXPECTED_NETWORK_TESTS`, keeping the membership assertion subset-shaped (every expected mark present, nothing unlisted marked)
- [x] 3. Sabotage loop RED: with one `@pytest.mark.network` removed from `tests/test_mac_trend_pick.py`, run `tests/test_check_model_links.py::test_the_network_membership_of_the_hf_data_path_files_is_exact` and record the RED run id + the `network-membership drift` case that fires (file `test_mac_trend_pick.py`, lost test `test_trend_on_a_48gb_mac_is_the_readme_list_with_metal_engines`)
- [x] 4. Restore the mark; verbatim-identical census test run now GREEN (record run id)
- [x] 5. `docs/changes.d/2026-11-02-census-mac-trend-pick-1132.md` fragment + `agent-wiki/2026-11-02-census-mac-trend-pick-1132.md` note (each referencing `#1132`; regenerated `CHANGES.md` row)
- [x] 6. `tests/test_check_model_links.py::test_the_network_membership_of_the_hf_data_path_files_is_exact` passes on this tree (census GREEN), and the branch is pushed to `origin`; PR opened against `asimov-agent/llgenie:main` (never a draft) = #1552
- [x] 7. Verified: `make lint`, `make check-docs`, `make check-wiring`, `make check-pr-hygiene`, `make openspec-validate NAME=census-data-path-files-mactrend-pick`, and `make openspec-tasks-check` (now that every task above is ticked) all exit 0
