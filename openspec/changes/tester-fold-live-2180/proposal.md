# tester-fold-live-2180 — proposal

Issue: [#2180](https://github.com/asimov-agent/llgenie/issues/2180)

## Why

`agents/llgenie-tester/` is this lane's versioned source of truth (#791) but its tree copy does not
match the live profile. Measured at `origin/main` `005d457` with `make sync-agent-profile
PROFILE=llgenie-tester CHECK=1`: **4 of 9 file(s) differ**. Three of those are TRUNCATED in the tree —
the tree copy is a prefix of the live rulebook (`live-longer` / `live-edited-not-tree`), so a blind
tree→live sync (the comparator's one-way direction) would destroy live behaviour (#2084-class), and a
rebuild from the tree would silently downgrade the lane. The live profile is the content of record —
it is the behaviour the lane actually runs.

## What Changes

- Three tree-truncated files copied live→tree byte-identically (fold live→tree FIRST, before any
  tree→live sync):
  - `skills/llgenie-pr-testing/SKILL.md` (100,420 → 100,563 b),
  - `skills/llgenie-pr-testing/references/post-merge-verification.md` (8,706 → 10,353 b),
  - `skills/llgenie-pr-testing/references/red-job-triage.md` (15,370 → 18,782 b).
- Five SKILL-linked live-only references copied live→tree byte-identically so the folded SKILL.md
  stays internally consistent (`gh-command-mechanics.md`, `monitoring-ci-runs.md`,
  `own-domain-audit.md`, `pr-state-inspection.md`, `verification-evidence-persistence.md`).
- `SOUL.md` is the opposite case — live is SHORTER (10,507 b) than the tree (13,634 b), so the tree
  appears newer; it is **kept from the tree** (not folded, diff empty for it).
- Change-note trio (#1123): `agent-wiki/2026-11-09-tester-fold-live-2180.md` +
  `docs/changes.d/2026-11-09-tester-fold-live-2180.md` + `CHANGES.md` regen.
- Text-only change under `agents/llgenie-tester/`; no gate, script, renderer, or merge rule change.
  Live-only `issue-domain-audit.md`, `pr-body-gates.md`, `profile-parity-measurement.md` and
  `scripts/fold-live-profile.py` are NOT SKILL-linked and out of this fold's scope — each rides its
  own single-file tracker vehicle.

## What Doesn't Change

- No behavioural change to the lane's rules — this is a content sync of rules that already run live.
- No `SOUL.md` edit. The `0 of 9 differ` comparator verdict falls to the post-merge tree→live sync
  (the owner lane's obligation, flagged via the PR's `SYNC:` body line), not to this fold commit.
