# data-path-files-census

## ADDED Requirements

### Requirement: the routing census roster lists every live-Hub test file, including tests/test_mac_trend_pick.py

The routing census in `tests/test_check_model_links.py` MUST list `tests/test_mac_trend_pick.py` in
its `DATA_PATH_FILES` roster, and MUST pin the file's seven `@pytest.mark.network` test names in
`EXPECTED_NETWORK_TESTS`, so the census's membership test scans the file and the routing of every
live-Hub reach in it is asserted. The membership assertion MUST keep the existing subset-membership
shape (every expected mark exists and nothing outside the ownership set carries a mark) — never a
strict equality over a fixed test list that reds on the next legitimate addition.

WHEN the census membership test runs on a tree where `tests/test_mac_trend_pick.py` carries its seven
`@pytest.mark.network` marks in `EXPECTED_NETWORK_TESTS`
THEN the census passes, because every expected mark is present and no unlisted file carries a mark.

#### Scenario: a live-Hub test in the newly-listed file reds the census by file and test

- **Given** `tests/test_mac_trend_pick.py` is listed in `DATA_PATH_FILES` and its seven
  `@pytest.mark.network` tests are listed in `EXPECTED_NETWORK_TESTS`
- **When** one of those `@pytest.mark.network` marks is removed from the file (silently routing a Hub
  call back into the hermetic gate)
- **Then** the census test `test_the_network_membership_of_the_hf_data_path_files_is_exact` exits
  non-zero with a `network-membership drift` message naming `tests/test_mac_trend_pick.py` and the
  test that lost its mark
- **Test:** runs `tests/test_check_model_links.py::test_the_network_membership_of_the_hf_data_path_files_is_exact`
  against a tree with one mark removed (the sabotage loop) — RED, then GREEN once restored

#### Scenario: a new legitimate addition does not red the census

- **Given** `tests/test_mac_trend_pick.py` is listed in `DATA_PATH_FILES` and its seven marks in
  `EXPECTED_NETWORK_TESTS`
- **When** a new `@pytest.mark.network`-carrying test is added to the file and to `EXPECTED_NETWORK_TESTS`
- **Then** the census stays GREEN, because the membership assertion is subset-shaped (every expected
  mark present, nothing unlisted marked) rather than a fixed exact-list equality
- **Test:** `tests/test_check_model_links.py::test_the_network_membership_of_the_hf_data_path_files_is_exact`

#### Scenario: the pristine tree keeps the census green

- **Given** the current `main` tree with `tests/test_mac_trend_pick.py` and its seven marks listed in
  the census
- **When** the census membership test runs
- **Then** it passes and the file is covered by the routing census (no hidden live Hub reach)
- **Test:** `tests/test_check_model_links.py::test_the_network_membership_of_the_hf_data_path_files_is_exact`
