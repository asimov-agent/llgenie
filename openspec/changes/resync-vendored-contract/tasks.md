# Tasks — resync-vendored-contract

- [x] measured the upstream edit: `447a9fa83` (2026-11-13T03:09Z, upstream issue #652) added the optional `measurement_model_aliases` row property to `data/model_contract.json` on master; `41539762d` (12:42Z) applied it to one row (`qwen3.6-35b-a3b` -> `["qwen3.8-27b"]`)
- [x] measured the red streak: `ci-hf-live` was last green at run 699 (11-13T01:13Z head `ec3ca5af4`); red on every run 700..723 since, all on `test_the_vendored_contract_is_upstreams_and_the_store_satisfies_it`
- [x] `data/model_contract.json` re-vendored byte-for-byte from upstream master (16,721 B, sha256 d312636c8ab5)
- [x] `data/MODEL_CONTRACT.md` re-vendored byte-for-byte from upstream master (8,245 B, sha256 6a1a0ea1e565)
- [x] live byte-identity + store-satisfaction test green against the re-vendored pair: `pytest tests/test_trend_pick.py::test_the_vendored_contract_is_upstreams_and_the_store_satisfies_it -m network` 1 passed rc=0 in the test container
- [x] hermetic twins green: `tests/test_trend_pick.py` + `tests/test_check_consults_measurements.py` battery in the test container at the lane head (98 passed rc=0)
- [x] the pair is paid: `agent-wiki/` note, `docs/changes.d/` row, rebuilt `CHANGES.md`, `make check-docs` green (rc=0 in the lane)
- [x] `make openspec-validate NAME=resync-vendored-contract` exits 0
- [x] `make test-unit` exits 0 at the final lane head (rc=0, 3765 passed, 13201 deselected, 16:18)
- [x] `make lane-preflight` prints `preflight: OK` on the pushed tree
- [x] issue #2646 body, PR body, and commit text carry the identical ticked acceptance block (issue body read back at 21:21Z with 4 ticked items; commit block and PR body carry the identical wording)
