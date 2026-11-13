# registry-sync — delta for resync-vendored-contract

## ADDED Requirements

### Requirement: The contract pair resyncs on its own when upstream edits it additively

When upstream's `data/model_contract.json` or `data/MODEL_CONTRACT.md` moves ahead of the
vendored pair with an ADDITIVE edit (a new optional key, new prose), the repo SHALL re-vendor
the contract pair byte-for-byte without waiting on the full store sync, and the additive-only
registry guard over `data/models.json` SHALL stay intact. A store that upstream shrank (a
blocked full sync, issue #2503) must not pin the contract pair to stale bytes: the contract is
what every stored row is validated against, and the live byte-identity test
(`make test-unit-network`) is red main while the pair lags.

#### Scenario: an upstream additive contract edit lands as a contract-only PR

- **WHEN** upstream adds an optional row property to the contract
- **THEN** a lane re-vendors `data/model_contract.json` and `data/MODEL_CONTRACT.md` byte-for-byte
- **AND** `data/models.json` and the derived tables are untouched
- **AND** the hermetic twin test and the live byte-identity test both pass at the lane head
