# Delta: registry-sync (sync-registry-alias-lock)

## ADDED Requirements

### Requirement: The alias row property survives normalisation, locked by a test
The vendored store pipeline SHALL preserve the optional per-row `measurement_model_aliases`
property (upstream contract `447a9fa83`) through `sync_registry.normalise()` when an upstream row
carries it, SHALL NOT synthesize it on rows that lack it, and a hermetic test SHALL lock this
behaviour so a row-rebuild refactor cannot silently drop the key.

#### Scenario: alias-carrying row keeps its attribution
- **WHEN** a synthetic upstream row carrying `measurement_model_aliases: ["other-id"]` is normalised
- **THEN** the normalised row carries the identical list, unchanged

#### Scenario: alias-free rows gain nothing
- **WHEN** a store whose rows carry no `measurement_model_aliases` is normalised
- **THEN** no normalised row gains the key

#### Scenario: the additive guard sees no alias loss
- **WHEN** `registry_keys.compare()` compares a committed store without the key against the
  normalised store where one row carries it
- **THEN** no reported loss names `measurement_model_aliases`
