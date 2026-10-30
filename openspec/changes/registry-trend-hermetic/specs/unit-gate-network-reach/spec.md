## ADDED Requirements

### Requirement: unit-gate-detects-a-non-hub-live-fetch

`tests/test_network_marker.py` SHALL fail when a scope of the hermetic selection can reach a **remote
network host** — a host other than the Hub included — through a helper module, unless that scope is
`@pytest.mark.network`-marked, already de-selected by `tests/fixtures/unit-suite.json`, or replaces
the transport itself (a stubbed `urlopen`). The failure message SHALL name the host it saw and the
`module.function` that reaches it.

#### Scenario: an unmarked test reaches a non-Hub host through a helper module

- **Given** a test module that calls `sync_registry.sync`, whose body reaches
  `raw.githubusercontent.com` through `fetch` → `urllib.request.urlopen`
- **When** the widened scan runs over the hermetic selection
- **Then** it names `raw.githubusercontent.com` and `sync_registry.sync` for that test, and the gate
  fails instead of running a live fetch on every `ci-unit` run
- **Test:** `tests/test_network_marker.py::test_no_unmarked_remote_fetch_enters_the_gate`

#### Scenario: the requested fixture is what reaches the network

- **Given** a module-scoped `live_sync` fixture that downloads upstream, requested only by unmarked tests
- **When** those tests are scanned
- **Then** each is named `(via fixture live_sync)` with the host, so marking the tests — not the
  fixture — is shown to be the fix
- **Test:** `tests/test_network_marker.py::test_the_remote_reach_scan_reds_on_a_non_hub_fetch_through_a_helper_module`

### Requirement: the-network-marker-owns-every-live-fetch

Every test that performs a real fetch to any remote host SHALL carry `@pytest.mark.network`, so
`make test-unit` (`-m "not network"`) executes none of them and `make test-unit-network`
(`ci-hf-live.yml`) owns them — and the behaviour they assert SHALL still be asserted hermetically
against a committed fixture where it can be.

#### Scenario: the trend-registry sync moves to the network pipeline, its twin stays

- **Given** `tests/test_registry_sync_trend.py`, whose live tests downloaded the upstream registry
- **When** `make test-unit` runs
- **Then** neither live test executes, and the vendored twins assert the identical ranking behaviour
  against `data/models.json` + `data/trending-README.md`
- **Test:** `tests/test_registry_sync_trend.py::test_the_vendored_store_adopts_a_higher_skilled_tps_for_models_that_fit_48gb`,
  `tests/test_registry_sync_trend.py::test_the_vendored_store_rank_follows_the_given_vram_ram_and_arch`

#### Scenario: the routing census cannot drift back

- **Given** the ownership census in `tests/test_check_model_links.py`
- **When** a mark is added to, or removed from, `test_registry_sync_trend.py` or `test_trend_pick.py`
- **Then** the census fails and names the drift, so a live fetch cannot silently return to the gate
- **Test:** `tests/test_check_model_links.py::test_the_network_membership_of_the_hf_data_path_files_is_exact`

#### Scenario: a conditional helper handed a committed path is a local read

- **Given** a helper that opens a URL only when its argument is one (`load_registry(src)`)
- **When** a hermetic test calls it with a committed path
- **Then** the scan reports nothing for that call, and reports the host when the same helper is handed
  a live URL
- **Test:** `tests/test_network_marker.py::test_the_remote_reach_scan_reds_on_a_non_hub_fetch_through_a_helper_module`
