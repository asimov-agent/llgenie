# Tasks: sync-registry-alias-lock

- [x] Rewrite issue #2647's body to the measured facts (normalise() preserves via whole-row copies; the deliverable is the lock test) with the six-section shape
- [x] Prove the live end-to-end fact it now claims: full CLI sync vs live upstream accepted rc=0 (models=118), the synced store carries qwen3.6-35b-a3b -> ['qwen3.8-27b'], registry_keys.compare reports 0 alias-related losses (24 drift lines belong to #2503)
- [x] Add the hermetic alias-lock test to tests/test_registry_normalise.py (preservation, no-synthesis, registry_keys.compare 0 alias losses)
- [x] Replay the test suite in the container (focused + full `make test-unit`) at the lane head, rc=0
- [x] `make openspec-validate NAME=sync-registry-alias-lock` exits 0
- [x] The commit carries the ticked AC mirror + `closes #2647`; `make lane-preflight` prints preflight: OK
