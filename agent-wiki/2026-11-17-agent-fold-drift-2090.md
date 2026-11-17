# agent-fold-drift-2090 — reconciling the last four flagged lanes (issue #2090, decision on #1079)

## What was measured

`make -s check-agent-profiles` on main `6787a657b6` (2026-11-17, after #2882/#2878/#2884/#2895
merged) prints 5 findings. The issue's 2026-11-08 denominator (586 findings, 11 lanes) has collapsed
to four in-scope lanes plus the planner lane, which belongs to #2084:

| lane | gate finding | verified reconciliation |
| --- | --- | --- |
| llgenie-documentation-maintainer | live SKILL.md 100,163 chars vs tree 99,944 | live's only unique content is the stale-snapshot rule inlined; the tree carries it in `references/merged-ci-verification.md` — tree is the cap-safe superset; sync tree→live, bump `1.0.25` |
| llgenie-engine-improver | live SKILL.md 107,070 b, "402 lines the tree lacks" | the live inline block equals the tree's `references/test-ci-refactor-method.md` exactly (`+0` live-only lines in the line-set diff); live had inlined the reference and lost the file; tree SKILL 60,565 b + ref 46,854 b, all under the 100k writer limit; sync tree→live, bump `1.0.1` |
| llgenie-pr-reviever | tree holds 1 line live doesn't | the tree line names `.github/workflows/ci-verdict.yml`; the live copy still names the retired `ci-requeue.yml` (#2702) — tree is newer; sync tree→live, bump `1.28.1` |
| llgenie-issse-implementer | `skills/bulk-mechanical-migration/` absent from tree | #2878 versioned this exact skill at its category path and refused the flat shadow (a second copy reddens `test_no_lane_tree_carries_the_same_skill_identity_twice`, #2836); the finding is a live-side duplicate identity — remove the live shadow, never a second tree copy |

## Key decisions

- Direction per lane is chosen by a line-set comparison, not by mtime: docs/engine-improver trees are
  semantic supersets (live-only text verified present in `references/`), so sync (tree→live) loses no
  rule; pr-reviever's live copy is stale, so the tree wins outright.
- The issse flat shadow is a duplicate-identity, and #2878's spec already ruled that a second tree copy
  reddens `test_no_lane_tree_carries_the_same_skill_identity_twice`. Reconciliation is live-side removal.
- #1079's vehicle question is decided, not built: the standing fold-lane pattern (#2882/#2878/#2884)
  plus `make check-agent-profiles` / `make agent-profiles-report` are the mechanism its acceptance asked
  for; the merge-tree/ratchet/fork-fetch method is committed at
  `agents/llgenie-engine-improver/skills/llgenie-engine-improver/references/test-ci-refactor-method.md`.
  #1079 closed as decided with its three acceptance items mapped to those artifacts.
- #2090 is not closed by this lane: AC9 (gate prints zero findings fleet-wide) still needs the planner
  lane, which is #2084's own objective.

## Current status

Tree carries the three version bumps; live-side reconciliation ran after the commit (deliberate
`sync-agent-profile --force` for the three lanes after their recorded comparisons, live shadow removed).
Post-land `make agent-profiles-report` shows zero findings for all four lanes; only the planner (#2084)
finding remains.
