## 1. Fold the 32 live-only lines live->tree
- [x] 1.1 Append the 17 live-only pitfall bullets verbatim to `references/pitfalls.md` and the 15-line verdict/salvage block verbatim to `references/rebase-verification-and-verdict.md`; add the two SKILL.md pointer lines; bump frontmatter version 1.0.0 -> 1.1.0; keep the tree-only `references/fleet-lane-side.md` pointer
- [x] 1.2 Prove zero loss: containment replay (every live-only line found byte-identical in the tree union) exits 0

## 2. Carry the change
- [x] 2.1 `agent-wiki/` note + `docs/changes.d/` fragment in the same commit, `make -s changes-index` clean
- [x] 2.2 Commit carries the fold, note, fragment, and this OpenSpec change (closes #2881)

## 3. Verify
- [x] 3.1 `pytest tests/test_agent_profiles.py` (tree-isolated guard) exits 0 and reports no `skill-size` finding for this lane
- [x] 3.2 `make -s check-docs` exits 0; `make openspec-validate NAME=agent-fold-prrebase-2090` exits 0; lane-preflight prints `preflight: OK`
