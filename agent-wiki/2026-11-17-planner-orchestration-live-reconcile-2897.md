# Reconcile the planner orchestration live copy onto its tree split shape (issue #2897, follow-up of #2090)

## What was verified against the spec

- The tree already carries the split shape: `agents/llgenie-planner/skills/llgenie-bot-orchestration/SKILL.md`
  body is 95,033 b (94,626 chars, under `SKILL_MAX_CHARS = 100_000`) with
  `references/filters-and-classifiers.md` (8,071 b) linked at SKILL.md:545 and :614. The earlier
  tree-side slimming (#2084, shipped via #2327/#2331/#2335/#2336; further slim #2853) wrote the
  content into the tree but never pushed the live copy, so the live `SKILL.md` stayed at 102,764 b —
  over the cap, unpatchable by `skill_manage`, and the last finding the drift gate names.
- Measured at PR head 1d0da3b698c55ecd4b522de05c90dce84b9f36e8 against main 6787a657: the line-set
  diff of the two SKILL.md files is +52 live-only / -0 tree-only, and all 39 content lines among the
  52 match `references/filters-and-classifiers.md` verbatim (measured 39/39). So the tree body +
  reference already version every live content line; the live copy is the only one over the cap.
- This change stamps the reconciliation in the tree: `version: 1.0.0 -> 1.0.1` in the planner
  orchestration `SKILL.md` frontmatter.

## Key decisions

- **The live write is a post-merge host step, not a CI/container action.** The live profiles live
  under `~/.hermes/profiles/llgenie-planner/` on the host; a CI runner or agent container has no live
  profiles (this change's `make -s check-agent-profiles` skips the live comparison audibly on a
  tree-only checkout). After this PR merges, the owner/lane runs the documented deliberate sync
  `make sync-agent-profile PROFILE=llgenie-planner FORCE=1` — the same shape the #1724 `SYNC:`-line
  contract asserts — which replaces the over-cap 102,764-b inline copy with the 95,033-b body plus
  `references/filters-and-classifiers.md`, no content lost (the 52 inline lines are the reference's
  39 content lines verbatim).
- Version 1.0.1 is the release stamp for that reconciliation: live body back under the cap ->
  patchable -> the gate can go zero fleet-wide (the 2026-11-08 baseline was 586 findings) ->
  #2090's fleet-wide-zero acceptance item ticks and #2090 closes.

## Current status

OpenSpec change `planner-orchestration-live-reconcile-2897` created and validated; tree carries the
1.0.1 stamp; `make check-agent-profiles`, `make check-docs`, `make lint` green. Live sync + the
zero-finding host proof land after merge on the host.
