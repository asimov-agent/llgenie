# #1634 — llgenie's registry sync follows the producer's #689 contract (`supported_engines`)

**Issue:** [#1634](https://github.com/asimov-agent/llgenie/issues/1634) · **Branch:** `llgenie-wt/1634-registry-revendor` · **Base:** `main@69b86b3b`

## What was wrong

The producing repo's `model_contract.json` (`04ad45c7`, 2026-11-02, "switch readers onto the
normalized measurement store #689 slice 2") deliberately promoted `supported_engines` to the only
required per-row model field and dropped `engines` from `required`; its `models.json` (`4465e933`,
#695) now emits every row with `supported_engines` and no per-row `engines`. llgenie's vendored
contract (last touched 2026-10-27, pre-#689) still required BOTH, and `sync_registry.py` hard-coded
the dropped field in two places:

- `validate()` looped per-row over `("id", "name", "vram_tier", "engines")` and demanded
  `engines` be a list of `{engine: ...}` rows — so **every** live row now failed
  `ValueError: models[0] (qwen3.8-27b) lacks 'engines'` at `scripts/sync_registry.py:77`, which redd
  the merge-to-main `hf-live` gate at the #1632 merge tip `69b86b3b` (run `41544259190`,
  job `125615887842`).
- `check_contract()` repeated the same hard-coded `m["engines"]` list/`engine`-row restatement,
  contradicting its own docstring "Every rule is READ from the schema, never restated here" — so a
  re-vendored contract alone would not have unblocked the gate.

## What changed

- `validate()` now requires `supported_engines` (the contract's required per-row field) instead of
  the dropped `engines`, and checks it is a list.
- `check_contract()` treats per-row `engines` (t/s measurements) as **optional**: it no longer forces
  the field, but validates any entry that is present against the schema's `engines.items.required`.
  The per-row required keys still come from `model_schema.required` (now `supported_engines`).
- `data/model_contract.json` re-vendored byte-for-byte from the producer's current contract (drops
  `engines` from per-row `required`) so the network test
  `test_the_vendored_contract_is_upstreams_and_the_store_satisfies_it` (which asserts vendored ==
  live byte-for-byte) passes.
- `tests/test_registry_normalise.py::_row` fixture now carries `supported_engines`, matching the
  contract it is validated against.

This is llgenie following upstream — the producing repo's #689 schema change is deliberate, so no
producing-repo data edit is owed for the `engines` field. The committed store already satisfies both
the committed and the LIVE contract with the change (verified hermetic container runs).

## Still open (out of this PR's scope — producing repo, TLL lane)

Separate from the `engines` contract: the producer's `models.json` **order** diverges from its own
README "Most loved" table at 24 positions on the #695 commit (`4465e933`);
`order_equal=True` at pre-#695 `04ad45c7`. That independently reds
`test_live_upstream_registry_is_the_live_readme_list` and the two `live_sync` ranking tests even with
my llgenie fix, because `sync()` enforces strict models-order==README-order. That is a producing-repo
data fix owned by the trending-local-llms lane.
