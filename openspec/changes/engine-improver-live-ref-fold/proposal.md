# Fold the engine-improver live profile references back into the tree (provisioning seam, #1740)

## Why

The engine-improver live profile and the committed tree under agents/llgenie-engine-improver/ must agree so the provisioning seam (#791/#1060/#1724) stays clean: the tree is the source the next provisioning reads, and make sync-agent-profile PROFILE=llgenie-engine-improver CHECK=1 reds whenever live and tree differ.

#1732 folded the bulk of the live profile into the tree, but FIVE files still drifted tree-vs-live: four references/ files (ci-run-watching.md, image-layer-caching.md, pr-gate-and-rebase-recovery.md, proving-and-pitfalls.md) and the profile own agent-profile-soul.md. The drift is invisible until a CHECK=1 run, so a stale tree silently provisions stale instructions.

## What Changes

- Fold the five drifted files live->tree VERBATIM (the live profile is the richer, newer copy; #791 drop-rule conservation refused to overwrite it with the older tree copy - the TREE is fixed, never the live profile shrunk).
- Regenerate CHANGES.md from fragments (make changes-index) so the fold change-note trio lands without a hand-edit of the rendered index.
- No product code, scripts, tests or workflows change; the fold is documentation of the engine-improver profile live behaviour into the committed tree.

## Benefit

make sync-agent-profile PROFILE=llgenie-engine-improver CHECK=1 reports no diff for the five files (tree == live), the provisioning seam is clean, and the next sync has nothing to conserve-overwrite.

## Not covered

- Live profile files for OTHER lanes remain that lane own fold finding (#1060 per-lane discipline).
- New engine work and any other issue are out of this PR scope.

## Technical

- agents/llgenie-engine-improver/skills/llgenie-engine-improver/references/{ci-run-watching,image-layer-caching,pr-gate-and-rebase-recovery,proving-and-pitfalls}.md
- agents/llgenie-engine-improver/agent-profile-soul.md
- change-note trio: agent-wiki/2026-11-05-engine-improver-live-ref-fold-1740.md, docs/changes.d/2026-11-05-engine-improver-live-ref-fold-1740.md, CHANGES.md (regenerated)
- measured at commit 6096b9ff; gate: make sync-agent-profile PROFILE=llgenie-engine-improver CHECK=1
