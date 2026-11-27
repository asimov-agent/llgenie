## ADDED Requirements

### Requirement: A named drift is handed to the filing path as an artifact

`check-trend-list-fresh`'s staleness read SHALL record the exact cells it named into
`build/trend-staleness-drift.json` when it exits 1, SHALL remove that artifact when a read comes back
fresh (exit 0), and SHALL NOT touch it when the read is unreadable (exit 2).

#### Scenario: Drift names its cells in the handoff

- **WHEN** `staleness_read` disagrees with the live trending and returns `(1, cells)`
- **THEN** `build/trend-staleness-drift.json` exists and carries exactly those cells

#### Scenario: A fresh read clears the handoff

- **WHEN** a later `staleness_read` returns `(0, [])` after a re-render
- **THEN** the handoff file is gone, so a stale drift can never be filed from it later

### Requirement: The filing path consumes the named drift without a second live build

`make trend-staleness-issue` SHALL file the drift found in the handoff without calling the live trending
build again, deduping on the drift fingerprint computed from those cells. It SHALL re-read live only when
no handoff exists (standalone invocation).

#### Scenario: Filing reuses the read the check already ran

- **WHEN** the handoff names a drift and the live build is stubbed to raise
- **THEN** `make trend-staleness-issue` files exactly one marker-deduped issue from the handoff cells and
  exits 0 without reaching the live build

### Requirement: A failed or unreadable filing leg is named and never exit 2 through the step

The `ci-hf-live` trend-staleness step SHALL guard the filing call so no filing-path failure ends the step
with exit 2: a filing failure prints the failing leg by name and exits 3. A standalone producer whose own
re-read cannot run SHALL print that fact by name before exiting 2.

#### Scenario: A named drift survives a Hub blip

- **WHEN** the check named a drift (exit 1, handoff written) and a second live read would fail
- **THEN** the step files the refresh issue from the handoff and does not conclude 2

#### Scenario: An unreadable standalone re-read is reported by name

- **WHEN** the producer runs with no handoff and its staleness re-read returns 2
- **THEN** the log carries the `[trend-staleness-issue] FAIL …` line naming the failed re-read and the
  exit code is 2
