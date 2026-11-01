# agents(planner): fold the residual live-ahead SOUL.md + nine orchestration references live→tree — bundle standard #1273

The planner's live profile is still ahead of the versioned tree in **10 files** (at `155ab8ba`):
`SOUL.md` (tree 16,175 b → live 16,962 b) and nine `llgenie-bot-orchestration/references/*.md`
(2,389–70,404 b tree → 3,728–87,753 b live). This is the residual the prior folds left: #1374 (the
SKILL.md fold), #1379 (ten whole-file references, `155ab8ba`) and the #1234 orchestration-ref fold
each brought their own files to `tree==live`, but these 9 reference files + SOUL.md were live-ahead
at the fold base and were not carried by any of those PRs.

The ten folded files (all copied verbatim live→tree, `cmp` byte-identical at the fold head):

SOUL.md · actions-run-attempt-reconciliation.md · ci-gate-vs-live-pipeline.md ·
closes-target-repointing.md · completion-integrity-check-handling.md · holds-and-closures.md ·
post-merge-verification.md · shell-and-body-safety.md · stalled-lane-and-dispatch-delivery.md ·
verifying-lane-claims.md

**Bundle-wide proof (measured 16:00Z at the fold head `155ab8ba`):**
`make sync-agent-profile PROFILE=llgenie-planner CHECK=1` rc 0 (`10 of 80 file(s) differ` → 0
differ), plus `cmp` per file live vs the committed tree copy. `tree==live` for the whole planner
bundle per #1273.

**Gates:** `make -s check-docs` rc 0 (census gate OK), `lint` rc 0, at the committed head.
Change-note pair ships in this PR (#1123).

`AGENTS:` preflight — base = origin/main `155ab8ba` (15:55Z fetch; read AGENTS.md at that sha:
small self-contained repo, make-target verification, doc-is-part-of-change + change→note gate all
honoured).
