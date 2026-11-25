# Spec Delta: trend-list-matrix-rerender-3056

## ADDED Requirements

### Requirement: the committed trend matrix agrees with the live trending on the landed commit

The committed matrix `tests/fixtures/trend-list-matrix.json` and the Hub answers it was rendered from
`tests/fixtures/hub-snapshot.json` SHALL be produced by one `make render-trend-list-matrix` run against
the LIVE trending, and `make check-trend-list-fresh` SHALL read rc=0 on `main` for that pair. A drift
that the staleness read names SHALL be closed by re-rendering the pair (never by editing a cell by
hand and never by widening the staleness read).

#### Scenario: the drift issue's cells are gone after the re-render

- **Given** issue #3056 names 4 disagreeing cells (`metal/24/8`, `metal/24/32`, `metal/24/60`,
  `metal/24/64`) from the `ci-hf-live` staleness step
- **When** `make render-trend-list-matrix` runs on a branch cut from the latest `main` and
  `make check-trend-list-matrix` and `make check-trend-list-fresh` run against its output
- **Then** both exit 0 and the live read reports no disagreeing cell
- **Test:** `tests/test_trend_list_matrix.py` (hermetic replay over the new pair, rc=0) plus the live
  read `make check-trend-list-fresh` (rc=0)

#### Scenario: the re-render changes data only

- **Given** a re-render branch that carries the new fixture+snapshot pair
- **When** `git diff --name-only origin/main...HEAD` is read on that branch
- **Then** every path is a render output (`tests/fixtures/trend-list-matrix.json`,
  `tests/fixtures/hub-snapshot.json`, `docs/trending-*.md`, `data/engine-skill-decisions.json`) and no
  script, workflow or test source is touched
- **Test:** measured in the lane's preflight record (no gate change ships with a data re-render)

## MODIFIED Requirements

None. The staleness read itself already shipped in the #2901 lane; this change carries only the
re-render of the cells issue #3056 names.
