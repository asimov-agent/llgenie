# Profile-sync drift after a SOUL/skills fold

When a lane reports `make sync-agent-profile PROFILE=<lane> CHECK=1` drift after a fold PR:

1. **Verify the drift is real, per-file.** Check each named reference file exists in the tree
   (`git cat-file -e origin/main:<path>`) and compare byte sizes tree-vs-live
   (`stat -c%s` on both). Live-only files (in live profile, absent from tree) and size-divergent
   files are the drift signature.
2. **The drop-rule is behaving correctly, not broken.** If live mtimes post-date the last fold
   commit's snapshot, sync *conserves* the live content and refuses to overwrite — tree stays
   behind, provisioning reads a stale tree. Do NOT "fix" sync to force-overwrite; conservation
   is the intended behavior.
3. **Remedy = a follow-up fold PR** under `agents/<lane>/`: copy live → tree for every drifted
   reference, then report `CHECK=1` clean (tree == live) at the PR head. Change-note trio
   (agent-wiki note + changes.d fragment + CHANGES.md row). One vehicle.
4. **Routing:** the planner files the refined six-section tracker (issue → PR → re-sync); the
   owning lane implements its own vehicle. No push while a fleet stop order / active engine-cell
   run stands.

## Stale "open set" claims

A lane may report a PR as still open from a snapshot taken before a close (e.g. a duplicate the
planner just closed). Re-sweep `gh pr list --state open --json number` before accepting any
live-open-set claim; `gh api .../pulls/<n> --jq '{state,merged,head:.head.sha}'` is the verdict.
A guard/ci-verdict red cited at a now-closed head is moot, not a live defect.
