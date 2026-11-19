## ADDED Requirements

### Requirement: The registry GC digest step parses the tool's real output format

The sweep tool `scripts/registry_cache_orphans.py` SHALL resolve an image ref to its manifest digest
by scanning the `docker buildx imagetools inspect` output with a tolerant match
(`digest:` followed by any whitespace and a `sha256:` hex run, case-insensitive), so both the
padded `Digest:` alignment printed by current buildx and the legacy single-space line resolve. When
no digest is present the tool SHALL refuse with its existing `no digest for <ref>` error.

#### Scenario: Padded real-world alignment resolves

- **WHEN** `digest_of` is given the verbatim inspect output line `Digest:    sha256:c5299a4136c4473606ff8eeedefd28ace2c783c05ee1f7e974b88de08bd36650`
- **THEN** it returns that full digest string

#### Scenario: Legacy single-space line still resolves

- **WHEN** `digest_of` is given an inspect output containing `digest: sha256:<hex>` with one space
- **THEN** it returns that digest string

#### Scenario: No digest refuses

- **WHEN** the inspect output carries no `digest:`-shaped line
- **THEN** `digest_of` exits with the message `no digest for <ref>` naming the ref, and the gc run
  counts that orphan as FAILED rather than deleting anything
