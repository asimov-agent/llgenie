# Fold live → tree for llgenie-ci-pipelines-maintainer's committed profile (issue #2170)

**Implements:** issue #2170. `agents/llgenie-ci-pipelines-maintainer/` is this lane's versioned
source of truth (#791), but 18 of 26 tracked files differed from the live host profile and the tree
copy was the truncated one — a rebuild from the tree would have silently downgraded the lane.

## What changed

Folded LIVE → TREE (the live profile is what the lane actually runs; the tree was the truncated
side), then committed the folded files, then synced TREE → LIVE and proved parity:

- **17 live-longer references** (tree was a truncated seed): took the live copy as the content of
  record — `agent-profiles`, `auto-merge-identity`, `change-note-gate`, `ci-job-selection`,
  `ci-verdict-rejudge-and-expiry`, `diagnosing-cancelled-runs`, `engine-build-cuda-cdi`,
  `hermetic-run-and-census-quirks`, `monitoring-check-rollups`, `pr-issue-linking-and-force-push`,
  `repo-artifact-conventions`, `runner-queue-diagnosis`, `shared-branch-coordination`,
  `verification`, `verifying-a-dispatch-premise`, `verifying-agent-tree-parity`,
  `verifying-planner-claims`.
- **SKILL.md**: took LIVE (edited 2026-11-09 after the tree's 2026-11-07 commit; its #2114 slimming
  had already moved the "When to Use" block into `references/when-to-use-and-pass-shape.md`, folded
  here), under the 100k cap so the skill-size exemption entry is deleted.
- **pipeline-map.md**: KEPT TREE — the tree reflects the post-#2293 manual-only state
  (`fix-bot.yml` / `run-failure-reactor.yml` = dispatch only), which is current; the live copy is
  the stale pre-#2293 auto-trigger table. Sync TREE → LIVE there is the legitimate direction.
- **87 live-only references + 1 live-only script** absent from the tree: folded into
  `agents/llgenie-ci-pipelines-maintainer/skills/llgenie-pipeline-maintenance/` so a rebuild carries
  them (previously unreviewable/unversioned behaviour).
- Deleted the now-stale skill-size-exemption entry for this lane's SKILL.md (back under 100k).

Measured at `54ff1145` after the fold: `make sync-agent-profile PROFILE=llgenie-ci-pipelines-maintainer CHECK=1`
reports the tree matches the live profile for the tracked set, and `make check-agent-profiles`
has no `live-longer` / `live-lines-missing` / `absent-from-tree` finding for this lane.

Not covered: provisioning at setup time is #2165; the obsolete `.hermes/skills` set is not deleted
here (no delete path by design); detecting cross-lane drift every pass is #2135.
