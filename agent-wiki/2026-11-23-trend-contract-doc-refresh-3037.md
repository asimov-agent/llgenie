# Trend contract doc half refreshed with the json half (issue #3037)

Date: 2026-11-23. Issue: #3037. OpenSpec change: `trend-contract-doc-refresh`.

## What was verified
- The `ci-hf-live` red on `main` is the live byte-identity guard, not trend-matrix drift: run
  `45244169021` (push, head `74b02fb40` = PR #3028) failed in `make test-unit-network` at
  `tests/test_trend_pick.py::test_the_vendored_contract_is_upstreams_and_the_store_satisfies_it`
  (`assert sr.VENDORED_CONTRACT_DOC.read_bytes() == upstream_doc`, first difference at byte 2680;
  1 failed, 13631 passed). In the same run `registry-liveness.yml` (`45244168907`) was green and
  `check-trend-list-matrix` was green (81 cases), so no committed matrix cell disagreed.
- Measured at `74b02fb40`: `data/model_contract.json` already equalled upstream's bytes
  (16721 == 16721, sha256 `d312636c8ab5`); only the human-readable half was stale — vendored
  `data/MODEL_CONTRACT.md` 8245 bytes against upstream's 8977 (25 unified-diff lines).
- `make -s sync-registry` re-vendored the doc half: it is now byte-identical to
  `https://raw.githubusercontent.com/andyholst/trending-local-llms/master/data/MODEL_CONTRACT.md`
  (sha256 `ffd3e437b3c6`), and the diff is exactly the four field-table changes upstream made
  — `hf` required -> not required, `engines` required -> not required (they live in
  `data/measurements.json` in the split store), plus the new optional `engine_aliases` and
  `measurement_model_aliases` rows. The contract rules (`cap: file-size-gb`,
  `selection: trending-build-ranks`, `tie-break: lower-file-size-gb-then-name`) are unchanged, so
  `data/models.json` and every derived artefact stayed untouched.
- The fixed render order ran in order and green: `make -s sync-registry` (rc=0) ->
  `make -s sync-quant-catalog` (rc=0) -> `make -s render-trend-list-matrix` (rc=0) ->
  `make -s render-engine-skill-gap` (rc=0) -> `make -s skills-validate` (rc=0); no new drop/keep
  line appeared, and the live sync re-recorded the Hub snapshots its own header says are recorded
  during a live sync (`tests/fixtures/hub-snapshot.json`,
  `tests/fixtures/quant-catalog-hub-snapshot.json`).
- The guard that filed this (#694) is the cause-level proof and it is NOT relaxed: at `main` it
  fails with the vendored doc 8245 bytes against upstream's 8977; the byte comparison stays.

## Key decisions
- The OpenSpec change adds the requirement the producer was missing to the `registry-sync`
  capability: when the trend contract is re-vendored, the DOC half refreshes in the same producer
  run as the json half, and the live guard test keeps comparing the vendored doc byte-for-byte with
  upstream. The fix is a data refresh through the producer, never a pin relaxation or a second code
  path.
- Out-of-scope work stays out and is linkable: the stale `data/model_contract.md` shim (640 bytes,
  no producer) is issue #3039, and running the hermetic trend-matrix comparison in the PR lanes
  instead of only post-merge on `main` is issue #3040.

## Current status
Branch `feat/trend-contract-doc-refresh` carries the OpenSpec change first, then the re-vendored
`data/MODEL_CONTRACT.md` plus the re-recorded Hub snapshots. The live guard test, the hermetic
batteries (`check-trend-list-matrix`, `check-quant-catalog`), `make test-unit` and
`make lane-preflight` are proven at the branch head before the PR to `asimov-agent/llgenie:main`
closes #3037; `make post-merge-live-check` is the landing record after the merge.
