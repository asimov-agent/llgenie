# status-keeper-fold-live-2179 — proposal

Issue: [#2179](https://github.com/asimov-agent/llgenie/issues/2179)

## Why

`make sync-agent-profile PROFILE=llgenie-status-keeper CHECK=1` at `origin/main` reports
`1 of 2 file(s) differ`, and the differing file is tree-truncated: `skills/llgenie-status-keeper/`
`SKILL.md` sits at 13,857 b in the tree against 28,919 b in the lane's live home (live v1.3.1 ahead
of tree v1.3.0). A blind tree→live sync (the comparator's one-way direction) would destroy
15,062 b of live behaviour (#2084-class); a rebuild from the tree would silently downgrade the lane.
The live profile is the content of record — it is the behaviour the lane actually runs.

## What Changes

- `agents/llgenie-status-keeper/skills/llgenie-status-keeper/SKILL.md` copied live→tree
  byte-identically (fold live→tree FIRST, before any tree→live sync).
- `SOUL.md` is already in parity (10,421 b both sides) — not touched.
- Both `host-bot-tools` marker blocks (live and committed tree) are the pinned form and
  byte-identical — no re-stamp required; the #1582 rendered-block gate stays green.
- Text-only change under `agents/llgenie-status-keeper/` plus the #1123 change-note trio
  (`agent-wiki/` note + `docs/changes.d/` fragment + `CHANGES.md` regen). No gate, script,
  renderer, or merge rule changes (#1644/#1088/#491 intact).

## What Doesn't Change

- No behavioural change to the lane's rules — this is a content sync of rules that already run
  live. No `SOUL.md` edit, no marker re-stamp, no openspec spec scenario (content sync).
