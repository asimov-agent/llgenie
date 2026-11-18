# trend-staleness

## ADDED Requirements

### Requirement: the trend matrix carries a live staleness read

`scripts/trend_list_matrix.py` MUST offer a `--staleness` mode that rebuilds the matrix against the
live Hub WITHOUT writing any fixture, compares it cell by cell against the committed
`tests/fixtures/trend-list-matrix.json`, prints every disagreeing cell (case key plus the rows that
added, dropped, or changed), and exits non-zero when any cell disagrees. A fixture that cannot be
read or a live build that cannot run exits 2 — an unreadable read never reports fresh.

#### Scenario: a drifted cell is named and the read is red

- **Given** the committed fixture pins a model at 13 GB and the live trending build reports 9 GB
- **When** `python3 scripts/trend_list_matrix.py --staleness` runs
- **Then** the disagreeing cell(s) are printed with their case key (`arch/vram/ram`) and the changed
  rows
- **And** the process exits non-zero
- **Test:** `tests/test_trend_list_matrix.py::test_staleness_names_the_disagreeing_cells_and_exits_nonzero`
  (fetch seam faked, comparison logic real)

#### Scenario: a fresh fixture reads green

- **Given** the committed fixture and a live build that agree in every cell
- **When** the staleness read runs
- **Then** it prints a fresh verdict naming the cell count and exits 0
- **Test:** `tests/test_trend_list_matrix.py::test_staleness_is_zero_when_every_cell_agrees`

#### Scenario: an unreadable stream is never a silent zero

- **Given** the fixture is missing or the live build raises
- **When** the staleness read runs
- **Then** it prints the failure on stderr and exits 2
- **Test:** `tests/test_trend_list_matrix.py::test_staleness_exits_2_on_an_unreadable_stream`

### Requirement: a staleness hit surfaces as a filed refresh issue from a monitor lane

A disagreement MUST be surfaced by an allow-listed monitor lane (no new schedule lane — the CI-schedule
allow-list of #2701 holds): the `ci-hf-live` lane runs `make check-trend-list-fresh`, and when the
read disagrees `scripts/trend_staleness_issue.py` files ONE open refresh issue naming the disagreeing
cells and ordering the re-render (`make render-trend-list-matrix`). The producer renders its body only
through `issue_body.render`, carries its dedupe marker as the body's first line, and is registered in
`issue_body.PRODUCERS`.

#### Scenario: the monitor lane files one deduped refresh issue per drift

- **Given** the staleness read disagrees in the `ci-hf-live` lane and no open refresh issue for the
  same fingerprint exists
- **When** the lane's staleness step runs
- **Then** exactly one open issue is filed, in the repository's six-section shape, whose body names
  the disagreeing cells and the re-render command
- **And** a second run with the same disagreement files nothing new (the marker read finds the open
  issue)
- **Test:** `tests/test_trend_staleness_issue.py::test_one_issue_per_drift_and_the_marker_dedupe`

#### Scenario: a green read files nothing

- **Given** the fixture agrees with the live build in every cell
- **When** the lane's staleness step runs
- **Then** no issue is filed and the step exits 0
