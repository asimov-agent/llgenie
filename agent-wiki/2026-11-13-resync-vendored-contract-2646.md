# Vendored contract resync after the upstream attribution edit (2026-11-13)

Branch `feat/resync-vendored-contract-2646`; issue #2646; PR closes #2646.

## What was verified

- `ci-hf-live` is red on main on every run 700..723 (since 2026-11-13T03:16Z), all on the
  byte-identity test `test_the_vendored_contract_is_upstreams_and_the_store_satisfies_it`.
  Last green: run 699 (11-13T01:13Z). Cause measured in the upstream repo: commit `447a9fa83`
  landed on trending-local-llms master at 03:09Z adding the optional
  `measurement_model_aliases` row property (upstream issue #652), and `41539762d` applied it
  to row `qwen3.6-35b-a3b` (`["qwen3.8-27b"]`) at 12:42Z.
- The lane re-vendors the contract pair byte-for-byte from master
  (`data/model_contract.json` 16,721 B; `data/MODEL_CONTRACT.md` 8,245 B) and touches no
  store file: the additive-only registry guard (#2503's blocked full sync) stays intact.
- The live test `pytest tests/test_trend_pick.py::test_the_vendored_contract_is_upstreams_and_the_store_satisfies_it
  -m network` is 1 passed, rc=0 at the lane head: vendored == upstream bytes, and the
  committed store satisfies the new contract (the new property is optional).

## Current status

OpenSpec change `resync-vendored-contract` validates; the lane ends with the three-mirror
acceptance block and a green, auto-mergeable PR. After the merge the next `ci-hf-live` run on
main sees byte-identity and goes green.
