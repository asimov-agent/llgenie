# llgenie-planner — #2174: live→tree profile fold

- **Date:** 2026-11-09 · **Issue:** #2174
- **Branch:** `agents/2174-planner-fold` (from `origin/main` `7f6850dd`)
- **PR:** the ready-for-review PR closing #2174 (base `main`)

## The gap

`make sync-agent-profile PROFILE=llgenie-planner CHECK=1` reported the tree copy of
`agents/llgenie-planner/` diverged from the live profile at `~/.hermes/profiles/llgenie-planner/`, with
several files whose tree copy was a truncated seed — a live→tree sync (the provisioning/rebuild
direction #2165) would have replaced live behaviour with the thinner copy, downgrading the lane with
no error (#2090-class). Direction for this lane is therefore **live→tree** where the tree is a genuine
truncated prefix of live: the live profile is the content of record, the repo copy the destination.

## What this PR folds

Folded **live → tree byte-for-byte** for the 9 references whose tree copy is a truncated prefix /
mid-file divergence (no hand-editing; live is strictly longer/current), verified `cmp`-identical at the
pushed head:

- **`skills/github-issue-triage/references/filing-a-well-formed-issue.md`** — divergence; live carries
  the extra `## 5. Prove the write` tail.
- **`skills/llgenie-bot-orchestration/references/acceptance-form-rule.md`** — live's
  `## File one body without a checklist` tail.
- **`skills/llgenie-bot-orchestration/references/auditing-lane-sync.md`** — live's
  `## What a gap means` tail.
- **`skills/llgenie-bot-orchestration/references/curator-live-drift-writer.md`** — **exact byte
  prefix missing its tail** (tree ended at line 16, live adds 9); live tail folded in.
- **`skills/llgenie-bot-orchestration/references/domain-ownership-dispatch.md`** — divergence; 29
  live lines absent, folded in.
- **`skills/llgenie-bot-orchestration/references/lane-role-audit.md`** — divergence; 19 live lines
  absent, folded in.
- **`skills/llgenie-bot-orchestration/references/llgenie-environment.md`** — divergence; 22 live
  lines absent, folded in.
- **`skills/llgenie-bot-orchestration/references/measurement-and-concurrency.md`** — divergence;
  2 live lines absent, folded in.
- **`skills/llgenie-bot-orchestration/references/worktree-and-push-hygiene.md`** — **exact byte
  prefix missing its tail** (tree ended at line 80, live adds 14); live tail folded in.

## KEPT at the tree copy (revert to main — not folded)

Per the planner's fold-direction ruling (issue comment 6743044363), the two skill files are **kept at
main's tree copies**, not folded live→tree:

- **`skills/llgenie-bot-orchestration/SKILL.md`** — main's tree copy is 98,179 B, deliberately kept
  under the 100,000-character skill-writer cap (#2118/#2145); folding the live copy (102,605 B)
  reintroduces the cap violation and pushes an un-patchable body into the profile on any tree→live
  sync. The live SKILL.md's 28 live-only reference-file pointers are live-side additions belonging to
  the separate lesson-versioning effort (#1079), not to this truncation fold.
- **`skills/github-issue-triage/SKILL.md`** — same ruling: the live copy's extra sections are
  live-side additions belonging to #1079; the tree copy stays the committed contract.

The tree-longer / tree-only files (e.g. `SOUL.md`, `prompts/llgenie-orchestrator-tick.md`,
`scripts/arm_pr.sh`/`delegate.sh`/`tick_board.sh`, `when-to-use-and-pass-shape.md`,
`measure_lane_idleness.py`) were intentionally **kept** — live has no extra behaviour there to fold
(issue step 4).

## Verification

- `cmp -s` tree-vs-live on all 9 folded references → **9/9 IDENTICAL** at the pushed head.
- `make check-agent-profiles` stays at its **main baseline** (the two kept-tree SKILL files remain
  under the 100k cap and carry no missing reference pointers; the residual live-longer rows for them
  are the #1079 drift class, not this fold).
- The change-note trio exists (`agent-wiki/2026-11-09-llgenie-planner-profile-fold-2174.md` +
  `docs/changes.d/2026-11-09-llgenie-planner-profile-fold-2174.md` + its regenerated `CHANGES.md` row);
  `make check-docs` is `ok`.

## Deliberately NOT part of this fold

The other live-only / truncated references and skills (`absent-from-tree` reference files, the two
further-truncated skill bodies) belong to issue #1079 (lesson-versioning) and the other lanes' own
drift issues (#2090 umbrella) — not this PR.
