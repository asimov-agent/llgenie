# Proposal: agent-fold-drift-2090

## Why

Issue #2090. Re-measured 2026-11-17 on main `6787a657b6` (after #2882/#2878/#2884/#2895 merged): `make -s check-agent-profiles` prints 5 findings, and the issue's 2026-11-08 measurement of 586 findings across 11 lanes has collapsed to four lanes still flagged:

- `llgenie-documentation-maintainer/skills/llgenie-docs-maintainer/SKILL.md` — live-longer (live 100,163 chars vs tree 99,944). Verified by diff: the live SKILL.md's only unique content is the 5-line stale-snapshot rule inlined into it; the tree carries that same rule in `references/merged-ci-verification.md` word-for-word (only the heading and quote prefixes differ). The tree is the semantic superset; a whole-file sync loses nothing.
- `llgenie-engine-improver/skills/llgenie-engine-improver/SKILL.md` — live-longer (live 107,070 b vs tree 60,565 b, "402 lines"). Verified by diff: the 404-line live inline block equals the tree's `references/test-ci-refactor-method.md` exactly (live adds nothing the reference lacks); the live profile had inlined the reference and lost the reference file. The tree keeps the cap-safe split (SKILL.md 60,565 b + reference 46,854 b, all files under the 100,000-char writer limit), so AC1's size requirement is met by the tree's existing shape.
- `llgenie-pr-reviever/.../references/review-recipes-by-pr-type.md` — the tree carries the current line (`Copy the whole env set from ... .github/workflows/ci-verdict.yml`), the live copy still names the retired `ci-requeue.yml` lane (#2702 deactivated it). The tree is the newer side; folding it backwards would version stale instruction. Sync (tree→live) is the reconciliation.
- `llgenie-issse-implementer/skills/bulk-mechanical-migration/SKILL.md` — the flat shadow #2878 deliberately did NOT copy into the tree (its skill identity is versioned once at the category path `skills/software-development/bulk-mechanical-migration/`; a second copy reddens `test_no_lane_tree_carries_the_same_skill_identity_twice`, the #2836 defect). The finding is a LIVE-side duplicate-identity, cleared by removing the shadow on the host, not by a second tree copy.

The issue's remaining lane ACs (pr-merge-conflict #2062 fold, tester lane, security/architect/status-keeper/business-analyst/product-manager) are already satisfied: the current gate prints zero findings for those lanes. AC9 (gate prints zero findings at all) needs the planner lane (#2084's own objective) and stays open. AC10's vehicle question (#1079) is decided by this change: the standing fold-lane pattern is the vehicle, and the audit command exists (`make check-agent-profiles`, `make agent-profiles-report`).

## What Changes

- Version bumps stamping the reconciliation: docs-maintainer `1.0.24 → 1.0.25`, engine-improver `1.0.0 → 1.0.1`, pr-review `1.28.0 → 1.28.1`. No semantic tree content changes: every flagged side is verified as a live-side duplicate, a live-side stale copy, or content the tree already carries in `references/`.
- Host-side reconciliation (the gate's own prescribed resolution, run after this lands): deliberate `make sync-agent-profile PROFILE=<lane> --force` for docs-maintainer, engine-improver and pr-reviever — after the per-lane literal/superset diffs above — and removal of the issse live shadow directory, so `make -s check-agent-profiles` prints zero findings for all four lanes.
- Close the vehicle question #1079 with its acceptance verified against the shipped artifacts: the `git merge-tree`/ratchet/fork-fetch method is committed under `agents/llgenie-engine-improver/skills/.../references/test-ci-refactor-method.md`; the batched-vehicle pattern is the proven fold-lane sequence (#2882/#2878/#2884); the audit command exists.
- Record the fold in `agent-wiki/` and a `docs/changes.d/` row (issue #2090).

## Impact

- Spec: new capability `agent-fold-drift-2090`.
- Code: three frontmatter version lines under `agents/**`, docs fragments, host-side profile reconciliation. No inference-engine behaviour, no CI semantics, no live-side content invention. Planner lane stays open under #2084; #2090's AC9 closes when the fleet-wide zero-findings state arrives.
