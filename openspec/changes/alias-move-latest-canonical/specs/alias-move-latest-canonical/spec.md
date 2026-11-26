# alias-move-latest-canonical Specification

## ADDED Requirements

### Requirement: canonical alias heal covers `:latest` too
When a lagging cell is the engine's canonical variant — as determined by
`engine_image.engine_latest_variant(engine_image.resolve(engine, None, variant))` — the alias mover
MUST publish the byte-identical fetched pin manifest to both `:<variant>` and `:latest`, and MUST
verify each moved tag at the committed pin digest through the same post-move probe.

#### Scenario: canonical cell heals both aliases
- GIVEN a lagging cell whose variant equals `engine_latest_variant` for that engine
- WHEN the mover fetches a manifest whose bytes hash to the committed pin
- THEN it PUTs those exact bytes to `/manifests/<variant>` and to `/manifests/latest` with the
  manifest's own mediaType, probes both tags, and reports both as MOVED at the pin digest

#### Scenario: non-canonical cell stays variant-only
- GIVEN a lagging cell whose variant is NOT `engine_latest_variant` for that engine
- WHEN the mover heals it
- THEN it PUTs the manifest only to `/manifests/<variant>` and probes only that alias

### Requirement: the move contract is unchanged
The mover MUST keep the four field contract (engine, variant, suffix, digest), the byte-preserving
`imagetools inspect --raw` fetch (never `imagetools create`), the mediaType guard, and the refusal
of a fetched body that does not hash to the pin. The `:latest` write MUST happen only after the
variant write and its digest verification succeed; a variant mismatch MUST publish nothing to
`:latest` and MUST NOT report a MOVED move.

#### Scenario: failed variant verification never touches `:latest`
- GIVEN a canonical cell whose variant PUT is accepted but whose post-move probe reads a different
  digest
- WHEN the mover finishes
- THEN it exits red with the digest mismatch, makes no `/manifests/latest` PUT, and probes no
  `:latest` tag

#### Scenario: bytes are identical on both tags
- GIVEN a canonical cell healed to both tags
- THEN the recorded PUT bodies for `/manifests/<variant>` and `/manifests/latest` are byte-for-byte
  equal to the fetched pin manifest and to each other
