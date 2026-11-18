# Planner live-side fold: clear the last profile-drift finding

## Why

Issue #2897. `make -s check-agent-profiles` at PR head `1d0da3b698c55ecd4b522de05c90dce84b9f36e8`
(measured against main `6787a657b6c59d2b95a0f4ae14b9151d2ef002a5`) prints exactly **1 finding** —
`llgenie-planner/skills/llgenie-bot-orchestration/SKILL.md`, live 102,764 b vs tree 95,033 b.
This is the last survivor of the 2026-11-08 586-finding list after issue #2090's four lanes closed.

The line-set diff is +52 live-only / -0 tree-only. All 39 live-only content lines match the tree's
`references/filters-and-classifiers.md` (8,071 b, linked from the tree body at SKILL.md:545 and
SKILL.md:614) verbatim, measured 39/39 — the live copy carries inline the block the tree already
split. Live is missing that reference file and sits over the 100,000-char skill-writer cap, so it
cannot be patched in place; the tree's split shape (95,033 b + reference) is the authoritative,
patchable, superset copy. #2084 closed with the tree-side fix but never reconciled the live side.

## What Changes

- Land the tree's split shape onto the live profile with the documented deliberate sync
  (`make -s sync-agent-profile PROFILE=llgenie-planner FORCE=1`); the 52 inline lines are carried
  by the tree reference, so the sync loses nothing (39/39 verbatim proof recorded before the write).
- Version-stamp the reconciliation: planner `SKILL.md` `version: 1.0.0 -> 1.0.1`.
- Record the fold: `agent-wiki/` note + `docs/changes.d/` row in the same commit.
- Prove the gate fleet-wide: `make -s check-agent-profiles` prints **0 findings** — the first time
  since the 2026-11-08 baseline of 586. This proof lands AFTER #2896 merges: while #2896 is open, a
  gate run at this lane's head must name exactly 1 finding, planner only (the four #2896 lanes drift
  live-vs-main until that PR lands).
- Correct `--force` to the script-side knob `FORCE=1` in the landed #2090 change's `spec.md`
  (after #2896 merges), so the merged spec names the knob `mk/agents.mk` actually implements.
- Close #2897 and complete #2090's fleet-wide-zero acceptance item (ticked with the gate proof).

## Impact

- Affected specs: `agent-profile-fold` (planner lane reconciled; fleet-wide zero findings becomes a
  proven gate state).
- Affected code: `agents/llgenie-planner/skills/llgenie-bot-orchestration/SKILL.md` (version line
  only), docs pair; live-side reconciliation (not in the tree).
