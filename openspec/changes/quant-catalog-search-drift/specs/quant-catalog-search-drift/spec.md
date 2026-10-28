# quant-catalog-search-drift

## ADDED Requirements

### Requirement: a dropped plan is classified by its own link, not by the search
When a committed plan is absent from a fresh generation, the gate MUST probe that plan's link and
MUST NOT fail on the absence itself: `ok` (200/206) and `gated` (401/403) are reachable and MUST be
reported as a NOTE that keeps the plan; only `dead` (404/410, or unverifiable) is a FAILURE.

WHEN the committed catalog records a plan the live search no longer returns
THEN `make check-quant-catalog` exits 0 when that plan's link answers 200/206 or 401/403
AND exits non-zero when it answers 404/410.

#### Scenario: a plan that fell off a search page but still resolves
- **Given** a committed plan whose URL answers 200, absent from the fresh generation
- **When** `compare()` runs with the production probe
- **Then** there are no failures and the note names the URL and `still reachable (ok)`
- **And** the note says the plan is kept, not a failure
- **Test:** `tests/test_quant_catalog_compare.py::test_a_plan_the_search_dropped_but_the_repo_still_serves_is_a_note_not_a_failure`

#### Scenario: a gated plan is reachable, never dead
- **Given** a committed plan whose URL answers 401/403, absent from the fresh generation
- **When** `compare()` runs
- **Then** there are no failures and the note names `still reachable (gated)`
- **Test:** `tests/test_quant_catalog_compare.py::test_a_gated_plan_the_search_dropped_is_also_kept`

#### Scenario: a plan nothing serves is still a failure
- **Given** a committed plan whose URL answers 404/410, absent from the fresh generation
- **When** `compare()` runs
- **Then** exactly one failure names the URL and `404/410` and says to drop it with `make sync-quant-catalog`
- **Test:** `tests/test_quant_catalog_compare.py::test_a_plan_whose_repo_answers_404_is_still_a_failure`

### Requirement: a sync keeps what is still downloadable
`make sync-quant-catalog` MUST carry a committed plan the live search no longer returns into the new
table when its link is reachable, MUST NOT carry a dead one, and MUST print both decisions.

WHEN the sync regenerates the table
THEN every reachable dropped plan is re-inserted into its own (model, engine) cell and printed as
`[sync] kept …` with the status that kept it
AND every dead one is left out and printed as `[sync] dropped … (the link answers 404/410)`.

#### Scenario: the still-public plan survives the sync
- **Given** a committed table with one reachable and one dead plan the generation dropped
- **When** `carry_over()` runs
- **Then** the reachable plan is in the payload, the dead one is not, both are reported
- **And** `compare()` on that payload against the same generation is green
- **Test:** `tests/test_quant_catalog_compare.py::test_the_sync_carries_the_reachable_plan_over_and_leaves_the_dead_one_out`

### Requirement: a clean catalog costs no request
The gate MUST probe only the plans a generation dropped, so an unchanged table makes no HTTP call.

WHEN the committed table equals the generation
THEN `compare()` returns no failures, no notes and calls no probe.

#### Scenario: an unchanged catalog probes nothing
- **Given** a committed table identical to the fresh generation
- **When** `compare()` runs with a probe the test counts
- **Then** there are no failures, no notes, and the probe was never called
- **Test:** `tests/test_quant_catalog_compare.py::test_a_clean_catalog_costs_no_probe`
