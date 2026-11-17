## 1. Land the lane's skill identity once, not twice
- [x] 1.1 Double-read the live shadow `skills/bulk-mechanical-migration/SKILL.md` (hash-stable,
      9327 b); re-measure the live category copy `skills/software-development/bulk-mechanical-migration/SKILL.md`
      (9807 b, sha256 `9e379c86…`) and prove it byte-identical to the tree copy versioned since
      #2238; resolve the shadow by NOT adding a second tree copy (measured: the flat copy reddened
      `test_no_lane_tree_carries_the_same_skill_identity_twice` at `f146ce1926`) and remove the flat
      tree copy this branch had briefly landed

## 2. Carry the change
- [x] 2.1 `agent-wiki/` note + `docs/changes.d/` fragment for the fold, `make -s changes-index` clean
- [x] 2.2 Commit carries the fold, note, fragment, and this OpenSpec change (closes #2877)

## 3. Verify
- [x] 3.1 `make sync-agent-profile PROFILE=llgenie-issse-implementer CHECK=1` exits 0 at the pushed head (no live write)
- [x] 3.2 `make -s check-agent-profiles` prints no `FAIL` row for `llgenie-issse-implementer`
- [x] 3.3 `make -s check-docs` exits 0; `make openspec-validate NAME=agent-fold-issse-bulk-migration` exits 0; lane-preflight prints `preflight: OK`
