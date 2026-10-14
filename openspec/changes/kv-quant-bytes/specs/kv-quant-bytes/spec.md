# KV cache sizing

## ADDED Requirements

### Requirement: Every documented KV cache type has an explicit size

The KV cache arithmetic SHALL size a type by an explicit bytes-per-element value, and every
KV cache type named in `skills/engines/*/SKILL.md` SHALL be representable. 8-bit types
(`q8_0`, `int8`) SHALL be 1 byte per element, i.e. exactly half the fp16 size; `k8v4` SHALL
be K 8-bit plus V 4-bit (0.75 bytes per element); `q4_0`/`q4_1`/`iq4_nl` SHALL stay 0.5 and
`q5_0`/`q5_1` SHALL be 5.5 bits (0.6875).

#### Scenario: an 8-bit cache is billed at half of fp16

- **GIVEN** the reported model's shape (48 layers, `n_head_kv=2`, key=value=256,
  `full_attention_interval=4`, `ctx_train=262144`)
- **WHEN** the per-token cache size is computed for `int8` and for `f16`
- **THEN** the `int8` value SHALL be exactly half the `f16` value
- **AND** the `int8` cache for 262,144 tokens SHALL be ≈3 GiB, not the ≈6 GiB the fp16
  fallback produced

#### Scenario: the table covers what the skills document

- **GIVEN** every `skills/engines/*/SKILL.md`
- **WHEN** the KV types each one names (e.g. strata's `--kv q4_0|int8|k8v4`) are collected
- **THEN** each type SHALL have an entry in the size table
- **AND** the test SHALL fail naming the skill and the unhandled type if one does not

### Requirement: An unknown KV cache type fails loudly

An unrecognised KV cache type SHALL raise an error naming the known types. The arithmetic
SHALL NOT fall back to the fp16 size for a type it cannot size, because that failure mode
doubles the bill and silently halves the servable context.

#### Scenario: a typo or unsupported type is an error, not fp16

- **WHEN** the per-token cache size is requested for a type that is not in the table
  (e.g. `q3_0`, `Q4_0`, an empty string, `None`)
- **THEN** a `ValueError` SHALL be raised
- **AND** the message SHALL name the known types

### Requirement: The launch and the budget arithmetic agree on the KV cache type

The KV cache type a launch serves SHALL be resolved once, from the card and the context, and
that single value SHALL be used by the offload decision, the emitted `-ctk`/`-ctv` flags, and
the plan printed for the user (including `--dry`). No helper SHALL use a bare module constant
for a type the launch also emits.

#### Scenario: the emitted flags are the resolved type

- **GIVEN** a model, a context and a card
- **WHEN** the launch command is built
- **THEN** `-ctk` and `-ctv` SHALL both carry the value the resolution function returns for
  that model, context and card
- **AND** `-c` SHALL carry the context the same resolution reported

#### Scenario: the plan shows the type and its size

- **WHEN** a serve plan is printed (with or without `--dry`)
- **THEN** the line SHALL name the KV cache type and the cache size in GiB for the context

#### Scenario: the offload decision uses the cache that is allocated

- **GIVEN** a card that holds every layer with the floor cache but not with the fp16 cache
- **WHEN** the layer count is computed for fp16 and for the floor type
- **THEN** the fp16 answer SHALL place fewer layers than the floor answer

### Requirement: The cache type is chosen explicitly and resolved once

A launch SHALL take the cache type from one resolution point. When the opt-in override
(`LLGENIE_KV_QUANT`) names a type, it SHALL be validated against the size table (an unknown
name SHALL be a loud error naming the known types) and honoured; when it is `auto`, the
resolution SHALL choose the largest type that fits the same budget; when it is unset the floor
SHALL be used, so no host changes behaviour by default. The resolved value SHALL be the one used
by the budget arithmetic, the offload decision, the emitted `-ctk`/`-ctv` flags and the printed
plan.

#### Scenario: unset keeps the floor

- **GIVEN** no override is set
- **WHEN** the type is resolved for any card
- **THEN** the answer SHALL be the floor type

#### Scenario: a named type is validated and served

- **GIVEN** the override names a type in the table (e.g. `int8`)
- **WHEN** the launch command is built
- **THEN** `-ctk` and `-ctv` SHALL carry that type
- **AND** the plan SHALL name it

#### Scenario: auto derives the largest that fits

- **GIVEN** the override is `auto`
- **WHEN** the type is resolved for a card that holds an 8-bit cache but not fp16
- **THEN** the answer SHALL be the 8-bit type

#### Scenario: an unknown override name is refused

- **GIVEN** the override names a type the table cannot size
- **WHEN** the type is resolved
- **THEN** a `ValueError` SHALL be raised naming the known types

#### Scenario: the override reaches the offload decision

- **GIVEN** the override asks for fp16 and a card with room only for the floor cache
- **WHEN** the launch command is built
- **THEN** `-ctk` SHALL be fp16
- **AND** `-ngl` SHALL be the layer count computed for the fp16 cache, not for the floor

### Requirement: A larger cache is available only through an explicit policy hook

The default policy SHALL keep serving the floor cache (`q4_0`), so existing behaviour is
unchanged. Deriving the largest type that fits the same budget SHALL be reachable only through
an explicit opt-in, which SHALL choose fp16, then 8-bit, then the floor, and never a type whose
cache does not fit the budget.

#### Scenario: the default is unchanged for a capable card

- **GIVEN** a card large enough to hold an fp16 cache
- **WHEN** the type is resolved without the opt-in
- **THEN** the answer SHALL be the floor type

#### Scenario: the opt-in picks the largest that fits

- **GIVEN** the same model and context, and cards sized to hold fp16 / only 8-bit / only the floor
- **WHEN** the type is resolved with the opt-in
- **THEN** the answers SHALL be `f16`, `q8_0`, and the floor type respectively
