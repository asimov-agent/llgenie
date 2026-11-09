# agent-profile-fold-2169 — proposal

Issue: [#2169](https://github.com/asimov-agent/llgenie/issues/2169)

## Why

`make sync-agent-profile PROFILE=llgenie-business-analyst CHECK=1` at `origin/main` `ffac2227`
reports `2 of 3 file(s) differ`: `skills/llgenie-business-analyst/SKILL.md` is tree-TRUNCATED
(7,604 b vs 14,136 b live) — a rebuild from the tree would materialise *less* behaviour than the
lane runs today (#2165-class). Folding live→tree restores the running behaviour so a rebuild cannot
downgrade the lane.

## What Changes

- `skills/llgenie-business-analyst/SKILL.md` folded live→tree byte-identically (7,604 → 14,136 b,
  full restore, not patched around the truncation).
- `SOUL.md` kept as the committed tree (12,283 b; live 9,156 b is behind — tree newer, sync grows
  live, allowed, #791 step 4 opposite case). `references/issue-body-shape.md` identical (1,931 b).
- #1123 change-note trio + this openspec change (`skip_specs: true`, content-sync fold) so the #1807
  openspec-presence gate for the `agents/` path is satisfied. `CHANGES.md` regenerated.

## What Doesn't Change

- No behavioural change to the lane's rules — this is a content sync of rules that already run live.
  No `SOUL.md` edit, no gate/script/renderer/merge-rule changes.
