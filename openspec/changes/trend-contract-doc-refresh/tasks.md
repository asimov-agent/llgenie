# Tasks — trend-contract-doc-refresh

## Implementation

- [x] Re-vendor the contract doc half: `make -s sync-registry` so `data/MODEL_CONTRACT.md` becomes upstream's bytes (8245 -> 8977) and `data/model_contract.json` stays byte-identical (16721); `data/models.json` and the derived store untouched. (rc=0; vendored doc sha256 `ffd3e437b3c6` == upstream's, json `d312636c8ab5` unchanged)

## Render order (post-merge discipline)

- [x] `make -s sync-quant-catalog` after the registry sync (no new drop/keep line introduced by the doc refresh). (rc=0; `make -s check-quant-catalog` rc=0 — the committed catalog still matches the generator)
- [x] `make -s render-trend-list-matrix` then `make -s render-engine-skill-gap` then `make -s skills-validate`, in that order. (rc=0 each; `make -s check-trend-list-matrix` rc=0 at 81 cases, `make -s skills-validate` rc=0 at 18 skills / 18 engines / 0 errors)

## Tests

- [x] Live byte-identity guard passes at the head, not skipped: `pytest tests/test_trend_pick.py::test_the_vendored_contract_is_upstreams_and_the_store_satisfies_it` and its hermetic twin `test_the_vendored_store_satisfies_the_vendored_contract`. (both pass in the `make -s test-unit-network` battery, rc=0 at the head; `tests/test_trend_pick.py` untouched)

## Verification (tick each with its replayable proof)

- [x] `make -s check-trend-list-matrix` exits 0. (rc=0)
- [x] `make -s check-quant-catalog` exits 0 (hermetic). (rc=0)
- [x] `make -s skills-validate` exits 0. (rc=0)
- [x] `make -s check-wiring` and `make -s check-package-layers` exit 0. (rc=0 / rc=0)
- [x] `make openspec-validate NAME=trend-contract-doc-refresh` exits 0. (rc=0)
- [x] `make lane-preflight` prints `preflight: OK`. (run at the final branch head, clean tree)
- [x] `make test-unit` exits 0 at the final branch head with zero skips. (run at the final branch head)
