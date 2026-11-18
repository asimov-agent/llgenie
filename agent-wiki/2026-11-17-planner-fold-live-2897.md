# 2026-11-17 — planner live-side fold (#2897, completes #2090's fleet-zero item)

Issue: #2897 (follow-up of #2090; completes the live side of the closed #2084). OpenSpec change:
`planner-fold-live-2897`.

## Measured baseline (before any write)

At PR head `1d0da3b698c55ecd4b522de05c90dce84b9f36e8` of #2090's lane, against main
`6787a657b6c59d2b95a0f4ae14b9151d2ef002a5`, `make -s check-agent-profiles` printed exactly 1
finding — the planner lane, the last survivor of the 2026-11-08 586-finding list.

| measure | value |
|---|---|
| live SKILL.md | 102,764 b (over the 100,000-char writer cap — unpatchable in place) |
| tree SKILL.md | 95,033 b (under cap; split shape) |
| line-set diff (difflib SequenceMatcher) | +52 live-only / -0 tree-only lines |
| live-only CONTENT lines | 39 (rest are blank/fence lines) |
| matched verbatim in tree `references/filters-and-classifiers.md` | **39/39** |
| reference size / links | 8,071 b; linked at SKILL.md:545 and SKILL.md:614 |
| live `references/` vs tree | live is **missing** `filters-and-classifiers.md` |
| versions | tree 1.0.0, live 1.0.0 |

## Decision

The tree is authoritative: every live-only lesson is already versioned there (39/39). Live is the
stale, over-cap, pre-split copy. Reconciliation direction is therefore the deliberate tree->live
sync `make -s sync-agent-profile PROFILE=llgenie-planner FORCE=1` (FORCE=1 is the script-side knob;
`--force` is consumed by make — mk/agents.mk), exactly the docs/engine-improver pattern from #2090.
No new tree copy of the block is created — the existing reference carries it. The tree version stamp
`1.0.0 -> 1.0.1` records that the split shape is now the live truth.

## Reconciliation and proof (to be recorded at the lane head)

- `make -s sync-agent-profile PROFILE=llgenie-planner FORCE=1` — live moves to 95,033 b +
  full reference set; the 52 inline lines remain carried by `references/filters-and-classifiers.md`.
- `make -s check-agent-profiles` at the lane head must print **0 findings** (first zero since the
  586-finding baseline); the proof gets ticked on #2897 and on #2090's fleet-wide-zero AC, and both
  issues close with the lane.

## Current status

Tree changes (version stamp + this note + changes.d row) land in the lane commit; live-side sync
runs after the commit, and the fleet-zero gate proof is posted on #2897/#2090 with the lane head.
