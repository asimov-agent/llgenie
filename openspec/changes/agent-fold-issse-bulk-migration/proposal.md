# Proposal: agent-fold-issse-bulk-migration

## Why

Issue #2877. Measured 2026-11-17 on main `bb29cc9994`: `make -s check-agent-profiles` reports 9
findings, and one is a live-only skill directory of the `llgenie-issse-implementer` lane —
`skills/bulk-mechanical-migration/` (1 file, 9327 b, live sha256 `2c5f8bb26a02…`) with no tree
counterpart at that path (#791, #2090 AC5). Re-measurement while folding showed the directory is a
DUPLICATE SHADOW: the same live profile also holds
`skills/software-development/bulk-mechanical-migration/SKILL.md` (9807 b, sha256 `9e379c86…`),
byte-identical to the tree copy of the same name versioned since #2238 (issue #2173's fold) and
carrying strictly MORE rules (the `Role artifact (2026-11-01)` section the shadow lacks). Copying
the shadow into the tree was measured to redden
`tests/test_provision_agent_profiles.py::test_no_lane_tree_carries_the_same_skill_identity_twice`
at head `f146ce1926` — the exact #2836 "two copies, one identity" defect. AGENTS.md requires every
change to be spec-tracked change-first.

## What Changes

- The lane's bulk-migration skill identity lands ONCE in the tree: the existing category copy
  `agents/llgenie-issse-implementer/skills/software-development/bulk-mechanical-migration/SKILL.md`
  (byte-identical to its live twin at its own path, verified at this head) is the versioned home.
  The flat shadow is NOT copied in — Hermes reads a lane's whole skills tree as one store, so a
  second copy of the same frontmatter name is an identity collision (#2836).
- Carry the lane's SOUL edit (live→tree, byte-identical) and the change note (`agent-wiki/` entry)
  and `docs/changes.d/` row in the same commit (the #1123 change→note gate).
- Prove at the pushed head: `make sync-agent-profile PROFILE=llgenie-issse-implementer CHECK=1`
  exits 0, `make -s check-agent-profiles` names no finding for this lane, and the duplicate-identity
  test exits 0. No live-side edit, no tree→live write.

## Impact

- Spec: new capability `issse-profile-folding`.
- Code: the lane's SOUL edit plus docs fragments under `agents/llgenie-issse-implementer/**` (no
  second skill copy); no inference-engine behaviour, no CI semantics, no other lane.
