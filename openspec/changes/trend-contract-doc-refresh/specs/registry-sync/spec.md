# registry-sync — delta for trend-contract-doc-refresh

## ADDED Requirements

### Requirement: the contract doc half refreshes on the same cadence as the contract json half

The vendored contract pair is two files: `data/model_contract.json` (what every stored row is
validated against) and `data/MODEL_CONTRACT.md` (the readable definition of a valid row). The repo
SHALL re-vendor the DOC half through `make -s sync-registry` whenever upstream's copy moves ahead
of the vendored bytes, on the same cadence as the JSON half — a doc-only drift is treated as a
contract drift, not as documentation debt. While the pair is out of sync, the byte-identity guard
(`tests/test_trend_pick.py::test_the_vendored_contract_is_upstreams_and_the_store_satisfies_it`,
the `make test-unit-network` battery that `ci-hf-live` runs on `main`) SHALL stay red and SHALL NOT
be widened, skipped, or narrowed to compare only the JSON half: the readable rules and the machine
rules must be the same revision, because a registry change written against the stale doc asserts
keys upstream no longer requires and omits keys ingest already supports.

The refresh SHALL be landed as its own data-only lane (issue -> OpenSpec change -> branch -> PR),
and it SHALL run the fixed render order the post-merge discipline pins so no downstream artifact
keeps a value read from the stale doc: `make -s sync-registry` -> `make -s sync-quant-catalog` ->
`make -s render-trend-list-matrix` -> `make -s render-engine-skill-gap` -> `make -s skills-validate`.

#### Scenario: an upstream doc-only contract edit lands as a doc-only data lane

- **WHEN** upstream's `data/MODEL_CONTRACT.md` differs from the vendored copy while `data/model_contract.json` is already byte-identical
- **THEN** the lane re-vendors `data/MODEL_CONTRACT.md` byte-for-byte from upstream through `make -s sync-registry`
- **AND** `data/models.json` and the derived store stay at their committed bytes
- **AND** the hermetic twin test and the live byte-identity test both pass at the lane head

#### Scenario: the refresh does not stop at the doc

- **WHEN** the vendored contract doc is re-vendored
- **THEN** the lane also completes `sync-quant-catalog`, `render-trend-list-matrix`, `render-engine-skill-gap` and `skills-validate` in that order with no downstream disagreement
- **AND** `make post-merge-live-check` reports `ci-hf-live.yml` with `conclusion=success` on `main` after the merge

- **Test:** `tests/test_trend_pick.py::test_the_vendored_contract_is_upstreams_and_the_store_satisfies_it` (live byte-identity, no skip), `tests/test_trend_pick.py::test_the_vendored_store_satisfies_the_vendored_contract` (hermetic twin)
