## ADDED Requirements

### Requirement: the alias-knobbed gate also compares the engine-level `:latest` alias digest
When the alias check is enabled, the committed-scope published-pin check SHALL, for every engine, additionally resolve the engine repo's `:latest` manifest exactly once and compare its digest with the committed pin-tag digest of the engine's CANONICAL variant cell — the cell decided by `engine_image.engine_latest_variant` (the same function `publish_refs` uses to append `:latest`), so publisher and gate can never disagree about who owns `:latest`. An aligned `:latest` SHALL print a `LATEST OK` line naming the ref; a `:latest` whose digest differs from the canonical cell's committed pin digest, or which resolves no manifest at all, SHALL print an `ALIAS LAG` line naming the ref and the reason, SHALL emit that canonical cell's `[select] <engine> <variant> <tag-suffix>` dispatch-contract line, and SHALL red the check.

#### Scenario: an aligned `:latest` stays green
- **WHEN** the knob is on and an engine's `:latest` digest equals its canonical cell's committed pin-tag digest
- **THEN** the check exits 0 for that engine and its output carries a `LATEST OK` line for the `:latest` ref.

#### Scenario: a lagging `:latest` selects the canonical cell for the moving push
- **WHEN** the knob is on and an engine's `:latest` resolves a manifest whose digest differs from its canonical cell's committed pin-tag digest
- **THEN** the check exits 1, prints `ALIAS LAG` naming the `:latest` ref and both digests, and prints the canonical cell's `[select]` line so the caller's dispatch machinery queues the exact repair (the moving sweep already republishes `:<variant>` and `:latest` for that cell).

#### Scenario: an absent `:latest` is a lag
- **WHEN** the knob is on, the canonical cell's committed pin tag resolves, and the engine's `:latest` resolves no manifest
- **THEN** the check exits 1 with an `ALIAS LAG` line stating `:latest` is absent and the canonical cell's `[select]` line.

#### Scenario: only the canonical variant cell owns the `:latest` check
- **WHEN** the knob is on and an engine has several enabled variant cells
- **THEN** `:latest` is probed exactly once for that engine, from the canonical (`cpu`-preferring, else first sorted params) variant's iteration, and a non-canonical cell's iteration probes no `:latest` ref.

#### Scenario: the engine-level check shares the variant-alias knob
- **WHEN** `ENGINE_PINS_ALIAS` is unset (every PR lane, `ci-hf-live`, every local run)
- **THEN** no `:latest` ref is probed and the verdict is unchanged tag-existence semantics; no second knob exists for the engine-level check.
