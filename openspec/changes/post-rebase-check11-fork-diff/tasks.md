# Tasks

- [x] Reproduce: the pre-fix check 11 reports `FAIL` on a clean rebase carrying only the branch's own edit (two sweep runs #2069, #2085)
- [x] Prove the discriminator in throwaway repos: a correct edit's gone lines are the branch's own deletions (PASS), a `-X theirs` revert's gone line is not (FAIL)
- [x] Rewrite check 11: compare base lines HEAD lacks against the branch's own diff (ORIG_HEAD vs merge-base(base, ORIG_HEAD)); NOTE for clear intent / no ORIG_HEAD, FAIL only for the provable revert
- [x] Rewrite `test-revert-detector.sh`: build real clean and `-X theirs` rebases; assert rc=0 / rc=1
- [x] Update `tests/test_rebase_lane_scripts.py` verdict-line assertions
- [x] Update the lane's SKILL.md + sweep-mechanics.md check-11 prose to the new discriminator
- [x] Change-note trio (`agent-wiki/`, `docs/changes.d/`, rendered `CHANGES.md`) + `check-docs` / `lint` / `check-wiring` / `check-workflows` green; two proofs quoted in the PR body
