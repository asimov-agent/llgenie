# agent-model-chain

## ADDED Requirements

### Requirement: Deliberate duplicate pin for the retired member

The base config SHALL name `tencent/hy4-flash:free` in the `nous-qwen4max` alias and in
`fallback_providers[2]`, with a YAML comment stating that this intentionally duplicates
`nous-hy4` / `fallback_providers[0]`. The 1000000 token budget SHALL be preserved.

#### Scenario: retired id has a live drop-in
- **WHEN** the chain is read from `agents/hermes-base-config.yaml`
- **THEN** no member names `qwen/qwen4-max:free`
- **AND** `nous-qwen4max` and `fallback_providers[2]` name `tencent/hy4-flash:free` with
  `context_window: 1000000`

## MODIFIED Requirements

### Requirement: Published budget equality

Each catalog-backed chain member's committed `context_window` SHALL equal the catalog's
published `context_length`. For `stepfun/step-3.7-flash:free` the id is retained and the
budget is 256000.

#### Scenario: stepfun budget matches the published length
- **WHEN** the catalog checker measures `stepfun/step-3.7-flash:free`
- **THEN** the committed `context_window` is 256000
- **AND** no `262144` budget remains in the base chain
