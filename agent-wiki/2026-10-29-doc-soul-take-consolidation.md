# Doc-SOUL take and dedupe consolidation onto one vehicle per file (2026-10-29)

The documentation lane completed its in-lane SOUL write (#1007, base `feat/agent-profile-implementer-skill`),
and the implementer (as the #919 tree owner) absorbed it and consolidated the overlapping dedupe efforts so
no file is changed by two vehicles at once.

- **Took the doc lane's file into the tree.** `git checkout origin/pr1007 -- agents/llgenie-documentation-maintainer/SOUL.md`
  (12,416 b, byte-for-byte from #1007 head `29de2456`). Measured with the gate's own functions: the doc fleet
  block is verbatim to `agents/standing-rules.md` (`_stated_block == fleet_block()` True), `_duplicate_rule_debts([])`,
  `_retired_rule_debts([])`. The doc lane's real additions (12 lane rules + the hold/hand-off section) sit outside
  the fence as the canonical rule intends.
- **Stripped #1008's doc-SOUL hunk.** #1008 had removed the same retired bullet + 3 duplicate restatements from
  the doc SOUL; with the take on #919 that is now one-vehicle-owned, so #1008 was rebuilt from #919's tip to
  dedupe only ci-pipelines, tester, pr-reviever. Verified 0 doc lines in its diff, `_retired []`, all-8 fences TRUE,
  only the planner's content-bearing `never-push` paragraph (its own SOUL) remains as duplicate debt.
- **Both branches' duplicate-report pins** updated to the post-take / post-dedupe contract: a cleaned lane
  (doc, implementer, and on #1008 also the three) must NOT be re-flagged; only the planner's paragraph may
  remain.

This is the #824 lesson applied forward: two PRs changing the same file is how a merge resolution drops content,
so the doc SOUL is owned by exactly one vehicle (the doc lane's in-lane write, held on #919), and the remaining
lanes' dedupe is #1008's reduced scope.

Referenced: `agents/llgenie-documentation-maintainer/SOUL.md`, `agents/{llgenie-ci-pipelines-maintainer,llgenie-tester,llgenie-pr-reviever}/SOUL.md`,
`tests/test_agent_profiles.py`, PRs #1007/#1006/#1008 on `asimov-agent/llgenie`.
