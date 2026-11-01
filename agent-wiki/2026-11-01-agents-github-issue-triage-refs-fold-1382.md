# agents(planner): fold github-issue-triage references live→tree — fix the #1374 fold-completeness gap (#1382)

PR #1374 (merged `fd3efd67`) folded `github-issue-triage/SKILL.md` live→tree but
**not** the three reference files that SKILL.md names — all three were
live-present / tree-absent on `origin/main`, so `scripts/check_agent_profiles.py
check` returned rc=1 there (`skill-reference-missing`). This PR completes the
bundle (standard #1273) by folding the three verbatim live→tree, byte-identical
(`cmp` rc 0 at the committed head): `references/bot-claim-and-branch-sweep.md`
(3,978 b), `references/filing-a-well-formed-issue.md` (3,325 b),
`references/no-pr-enumeration.md` (2,376 b).

Now the whole `github-issue-triage` skill is `tree==live` for the reference
subtree, and the planner-profile skill-reference-missing finding is cleared.

`AGENTS:` — base = origin/main `155ab8ba` (15:17Z fetch; AGENTS.md read at that
sha: small self-contained gguf-lookup repo, make-target verification, ghost-gate
discipline, no force-merge). Branch cut from the fetched tip. Closes #1382.

Change-note pair ships in this PR (#1123).
