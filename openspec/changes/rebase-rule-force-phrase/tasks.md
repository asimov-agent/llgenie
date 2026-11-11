# Tasks

- [x] 1. All 20 scoped files carry the corrected phrase byte-identically; grep for the stale tuple is CLEAN. Verified: AC2 grep in the PR body run + `git diff origin/main...HEAD` shows only that phrase in 20 files
- [x] 2. The rulebook tests that read these files still pass. Verified: `tests/test_agent_profiles.py`, `tests/test_pr_hygiene_sync_line.py`, `tests/test_rebase_lane_scripts.py` green in llgenie/test at this head
- [x] 3. Docs: `agent-wiki/2026-11-11-rebase-rule-force-phrase-2451.md` + `docs/changes.d/2026-11-11-rebase-rule-force-phrase-2451.md` + `make changes-index`, naming issue #2451 and the PR. Verified: `make check-docs`
- [x] 4. `make openspec-validate NAME=rebase-rule-force-phrase` exits 0 and `make lane-preflight` prints `preflight: OK` at the branch head
