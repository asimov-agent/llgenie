# Tasks — verify the lane behavioural contract (issue #2260)

- [x] Add `scripts/verify_lane_contract.py` (behavioural contract checker: six contract elements + own-duty DUTY map + skills-materialised axis, built from pathlib.Path.home(), `--root` override) and `make verify-lane-contract`
- [x] Wire the checker as orchestrator tick step 9 (VERIFY LANE RESPONSIBILITY) in `agents/llgenie-planner/prompts/llgenie-orchestrator-tick.md`, renumbering steps 9–13 to 10–14
- [x] Add hermetic tests `tests/test_verify_lane_contract.py` (complete-contract PASS; empty SOUL FAIL; missing report line FAIL; no-communication FAIL; archive-only skills FAIL; own-duty-marker-removed FAIL) — negative controls prove the gate is not a rubber stamp
- [x] Versioned under `scripts/` + `agents/llgenie-planner/`, wired through make, gated by check-wiring
- [x] Open the ready-for-review PR with `closes #2260`
