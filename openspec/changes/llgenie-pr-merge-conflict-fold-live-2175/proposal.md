# llgenie-pr-merge-conflict-fold-live-2175 — proposal

Issue: [#2175](https://github.com/asimov-agent/llgenie/issues/2175)

## Why

`make sync-agent-profile PROFILE=llgenie-pr-merge-conflict CHECK=1` at `origin/main` `e141cc9b68`
reports `10 of 29 file(s) differ` (the issue's own 7/28 table was stale — re-measured fresh at
10/29/2026). Five references are tree-truncated: folding live→tree restores the running behaviour so
a rebuild from the tree cannot downgrade the lane. Five other files are tree-LONGER — the previous
botched push `b97ac6a0` shaved those DOWN to live size; the correct resolution keeps the tree.

## What Changes

- 5 tree-truncated references folded live→tree byte-identically (`agents/llgenie-pr-merge-conflict/
  skills/llgenie-pr-rebase/references/{fork-pr-mechanical-rebase,hard-rules,measurement-and-readback,
  skill-script-hygiene,sweep-mechanics}.md`).
- 5 tree-longer files (`SKILL.md`, `post-rebase-verify.sh`, `salvage-audit.sh`, `stack-replay.sh`,
  `test-revert-detector.sh`) kept as the committed tree — not shaved to live.
- #1123 change-note trio + openspec change (`skip_specs: true`, content-sync fold) so the #1807
  openspec-presence gate for the `agents/` path is satisfied. `CHANGES.md` regenerated.

## What Doesn't Change

- No behavioural change to the lane's rules — this is a content sync of rules that already run live,
  plus the keep-tree files retain pre-existing tree behaviour. No `SOUL.md` edit, no gate/script/
  renderer/merge-rule changes (#1644/#1088/#491 intact).
