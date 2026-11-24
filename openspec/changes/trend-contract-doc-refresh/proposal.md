# Why

The newest `main` run of `ci-hf-live.yml` is red (run `45244169021`, event=push, head `74b02fb40` = PR #3028) in `make test-unit-network`: `tests/test_trend_pick.py::test_the_vendored_contract_is_upstreams_and_the_store_satisfies_it` fails at `assert sr.VENDORED_CONTRACT_DOC.read_bytes() == upstream_doc` (diff at byte 2680, `1 failed, 13631 passed`). Measured at `74b02fb40`: the machine contract `data/model_contract.json` IS upstream's bytes (16721 == 16721). Only the human-readable doc lags — vendored `data/MODEL_CONTRACT.md` is 8245 bytes against upstream's 8977 (25 unified-diff lines). Upstream changed its field table in four places: `hf` required -> not required, `engines` required -> not required, plus two new optional keys `engine_aliases` and `measurement_model_aliases`.

So the readable definition of a valid store row currently asserts two keys upstream no longer requires and omits two keys ingest already supports, and the post-merge live battery stays red, which blocks recording the landing of PR #3028 and blocks landing further changes onto `main`. The guard that filed this (#694, landed by the contract vendoring in the `registry-sync` lane) fired correctly; the refresh never followed it (issue #3037).

# What Changes

- ADDED `registry-sync`: the DOC half of the vendored contract pair (`data/MODEL_CONTRACT.md`) refreshes on the same cadence as the JSON half (`data/model_contract.json`) — a doc-only drift reddens `main` exactly like a contract drift and SHALL be landed as its own data-only lane through `make -s sync-registry`, with the byte-identity guard test untouched.
- Re-vendor `data/MODEL_CONTRACT.md` byte-for-byte from upstream master (8245 -> 8977 bytes) so it carries the four field-table changes (`hf` no, `engines` no, `engine_aliases`, `measurement_model_aliases`); `data/model_contract.json` remains byte-identical at 16721 bytes and `data/models.json` / the derived store are untouched.
- Run the fixed post-merge render order the discipline pins, so nothing downstream keeps a number read from the stale doc: `make -s sync-registry` -> `make -s sync-quant-catalog` -> `make -s render-trend-list-matrix` -> `make -s render-engine-skill-gap` -> `make -s skills-validate`.
- No gate widening: the byte-identity guard (`tests/test_trend_pick.py::test_the_vendored_contract_is_upstreams_and_the_store_satisfies_it`) and the additive-only registry guard are not relaxed.

# Impact

- Affected specs: `registry-sync` (ADDED: the contract DOC half resyncs on the same cadence as the JSON half).
- Affected data: `data/MODEL_CONTRACT.md` (and any downstream artifact the fixed render order legitimately re-derives).
- Affected gate: `make post-merge-live-check` reports `ci-hf-live.yml … conclusion=success` on `main` after the merge.
- No script, workflow, or engine change; no test is skipped or widened.
