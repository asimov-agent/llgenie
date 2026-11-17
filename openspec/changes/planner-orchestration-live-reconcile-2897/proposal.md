# Proposal: planner-orchestration-live-reconcile-2897

## Why

Issue #2897 (follow-up of #2090): the planner lane's live orchestration SKILL.md is over the
skill-writer cap again. Measured at PR head 1d0da3b698c55ecd4b522de05c90dce84b9f36e8 against
main 6787a657b6c59d2b95a0f4ae14b9151d2ef002a5, `make -s check-agent-profiles` prints one finding:
`llgenie-planner/skills/llgenie-bot-orchestration/SKILL.md`, live 102,764 b vs tree 95,033 b, +52
live-only lines (-0 tree-only). The tree's split shape (body + `references/filters-and-classifiers.md`,
8,071 b) already versions all 39 of those content lines verbatim — but the LIVE copy never received it,
so it stays over the cap, un-patchable by `skill_manage`, and the dashboard gate keeps naming this one
finding forever (the 2026-11-08 baseline was 586 findings; this is the last one).

## What Changes

This change carries the tree-side bookkeeping that lets the reconciliation land and stay honest:

1. Version-stamp the tree planner orchestration `SKILL.md` 1.0.0 -> 1.0.1, marking the release that
   carries the split shape (body + `references/filters-and-classifiers.md` already tree-linked at
   SKILL.md:545 and :614) as reconciled.
2. Land the reconciliation onto the live profile with the documented deliberate sync
   (`make sync-agent-profile PROFILE=llgenie-planner FORCE=1`) by the post-merge lane/owner, replacing
   the over-cap inline live copy with the 95,033-b body plus the reference file, no content lost
   (the 52 live inline lines are the reference's 39 content lines verbatim, measured 39/39).
3. Record the reconciliation in the tree: `agent-wiki/` note + `docs/changes.d/` fragment +
   `CHANGES.md` index row in the same commit, `make check-docs` green.

## Goals

The planner skill becomes patchable again (live back under the 100,000-char cap) and
`make -s check-agent-profiles` reads zero findings fleet-wide for the first time since the 2026-11-08
measurement — unticking #2090's fleet-wide-zero acceptance item so the umbrella can close. Out of
scope: the earlier tree-side slimming of the same body (#2084, shipped via #2327/#2331/#2335/#2336;
further slim #2853), which this change's live resolution completes.
