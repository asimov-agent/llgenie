# registry-sync-store

## ADDED Requirements

### Requirement: The vendored store and every derived table describe the same registry

The vendored `data/models.json` SHALL be the store upstream published (its `generated_utc` is the
store's own stamp), and every table derived from it — `data/trending-quant-catalog.json` and its
fixture, `tests/fixtures/trend-list-matrix.json`, `data/engine-skill-gap.json` — SHALL be the output
of its generator reading that store, never a hand-edited copy. `make check-registry` SHALL confirm
the store satisfies the vendored contract, that its README order matches it, and that the sync lost
nothing versus the committed copy.

WHEN the weekly sync rewrites the vendored store
THEN each generator rewrites its table from that store, and the checking targets agree with the
committed files.

#### Scenario: the regenerated tables match the store they were rendered from

Given the vendored store at `generated_utc` `2026-10-27T21:47:11Z` with 112 models and 43 engines
When  each generator's `--check` mode reads the committed tables
Then  every check exits 0: the registry satisfies its contract and lost nothing, the quant table
      and the trend-list matrix are exactly what their generators produce, and the gap file is current.

- **Test:** `make check-registry check-quant-catalog check-trend-list-matrix check-engine-skill-gap` (CI: `ci-unit`) and `tests/test_trend_list_matrix.py::test_trend_list_matches_the_committed_matrix`, `tests/test_registry_keys.py::test_real_vendored_registry_is_additive_against_itself`

### Requirement: An engine new to the store is shipped or decided with a dated reason

An engine named by `data/models.json` SHALL either have `skills/engines/<id>/SKILL.md` or a dated,
reasoned entry in `data/unsupported-engines.json` naming the upstream it was read from.
`make check-engine-skill-gap` SHALL fail naming an engine that has neither, and SHALL fail on a
decision that has gone stale (its engine now ships a skill, or upstream no longer lists it).

WHEN a store adds an engine llgenie does not ship
THEN the store is accepted only after that engine has a skill or a dated decision.

#### Scenario: a new engine the store lists is decided, and the gap is empty

Given the store's one new engine `Rapid-MLX` (backend `Metal`, upstream `raullenchai/Rapid-MLX`)
When  the gap gate reads the registry, the skills and the dated decisions
Then  `Rapid-MLX` resolves as `known-unsupported` from its dated `deferred` entry, the unresolved
      set is empty, and `make skills-validate` reports 0 errors over 43 engines.

- **Test:** `tests/test_engine_skill_gap.py::test_a_new_unskilled_engine_fails_the_gate_and_a_dated_decision_silences_it`, `tests/test_engine_skill_gap.py::test_the_real_files_are_current_and_the_gate_agrees_with_the_gap`
