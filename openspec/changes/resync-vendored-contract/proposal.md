# Re-vendor the model-contract pair after the upstream additive edit (issue #2646)

## Why

Upstream `trending-local-llms` (master) edited its contract: a new optional row property
`measurement_model_aliases` (array of STORE model ids, the documented exception to the
measurement-attribution refusal — upstream issue #652) was added after `supported_engines`,
and `MODEL_CONTRACT.md` grew its prose twin. The vendored pair in `data/` still carries the
pre-edit bytes (16,013 vs 16,721; 7,350 vs 8,245), so main's `ci-hf-live` network battery reds
`tests/test_trend_pick.py::test_the_vendored_contract_is_upstreams_and_the_store_satisfies_it`
(run 43499346068: byte-identity assert at index 15910, `1 failed, 13194 passed`).

The full-store re-sync stays blocked on its own lane (#2503): upstream also shrank
`models.json`, which the additive-only registry guard refuses. The contract pair is additive
on its own and must not wait on that review.

## What Changes

- `data/model_contract.json` and `data/MODEL_CONTRACT.md` are re-vendored byte-for-byte from
  upstream master.
- No store change: `data/models.json` and the derived tables stay at their committed bytes;
  the new contract property is optional, so every committed row remains valid (hermetic twin
  `test_the_vendored_store_satisfies_the_vendored_contract` and the live network test prove it).
- No gate widening: the additive-only registry guard is untouched.

## Impact

- Affected specs: `registry-sync` (ADDED: the contract pair resyncs on its own, decoupled from a
  blocked store sync).
- Affected data: `data/model_contract.json`, `data/MODEL_CONTRACT.md`.
- After the merge, the next `ci-hf-live` run on main sees byte-identity and goes green;
  `ci`/`ci-unit` are hermetic and stay green throughout.
