## ADDED Requirements

### Requirement: The committed quant catalog matches a fresh live regeneration

The committed `data/trending-quant-catalog.json` (and its recorded fixture `tests/fixtures/trending-quant-catalog.json` + `tests/fixtures/quant-catalog-hub-snapshot.json`) SHALL match what the generator produces from the live trending build, so that `make check-quant-catalog` (hermetic) and `make check-quant-catalog LIVE=1` (the `ci-hf-live` battery seam) are both green on `main`.

#### Scenario: Battery gate replay after a refresh

- **WHEN** the refresh chain `sync-registry` → `sync-quant-catalog` → `render-trend-list-matrix` → `render-engine-skill-gap` → `skills-validate` has run and its data deltas are committed
- **THEN** `make check-quant-catalog` exits 0 replaying the recorded Hub answers
- **AND** `make check-quant-catalog LIVE=1` exits 0 against the live Hub

#### Scenario: A new trending quant repository is carried into the committed catalog

- **WHEN** the live trending build reports a quant repository the committed catalog does not name (e.g. `nace-ai/Qwen3.8-27B-MLX` for `qwen3.8-27b`)
- **THEN** the refreshed committed catalog names it with its live-validated file links

#### Scenario: Still-reachable plans the live search dropped are kept, not dropped

- **WHEN** a committed plan link answers the probe with 200/206 but the live trending search no longer returns that repo
- **THEN** the sync keeps the plan and records a carry-over note rather than deleting the plan
