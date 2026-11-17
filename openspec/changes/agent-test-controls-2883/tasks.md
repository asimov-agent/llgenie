## 1. Ship the controls
- [x] 1.1 Copy `test-dirty-detector.py` + `test-tally-delta.py` from the live profile `scripts/` into `agents/llgenie-pr-merge-conflict/scripts/` byte-identical (sha256 pairs recorded)
- [x] 1.2 Prove parity: census (git-index read) reports both controls `same` and the live-only count drops 13 -> 11; sync CHECK parity re-measures at the landing head (this base predates the #2882 fold merge, so the live lane book legitimately drifts against it)

## 2. Carry the change
- [x] 2.1 `agent-wiki/` note + `docs/changes.d/` fragment in the same commit, `make -s changes-index` clean

## 3. Verify
- [x] 3.1 Both controls run green host-side against the tree copies (4/4 and 16/16, rc=0 recorded on #2883)
- [x] 3.2 `pytest tests/test_agent_profiles.py` exits 0; `make -s check-docs` exits 0; `make openspec-validate NAME=agent-test-controls-2883` exits 0; lane-preflight prints `preflight: OK`
