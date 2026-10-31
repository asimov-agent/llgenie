# 2026-10-31 — issue #1062: version the planner lane and add the post-merge verification duty

## What

The orchestrator's behaviour lived partly out-of-tree: the live `llgenie-planner` profile carried a SOUL
and a `llgenie-bot-orchestration` skill that the tree did not match byte-for-byte. `make sync-agent-profile
PROFILE=llgenie-planner CHECK=1` failed on 7 live-only references (absent from the tree), several live-longer
documents where the tree was a stale prefix, and the post-merge verification duty was missing from the SOUL
entirely. A credential-holding agent was running under instructions the tree could not vouch for.

## The change

- **Whole-lane mirror, live → tree**: pulled the planner's current live SOUL + `skills/llgenie-bot-orchestration`
  into `agents/llgenie-planner/` byte-identical (55 file(s), `CHECK=1` OK). Adds the 7 live-only references
  (`ceiling-config-verdict-vs-defect`, `change-note-gate`, `ci-gate-vs-live-pipeline`, `closes-target-repointing`,
  `completion-gate-and-test-run`, `curator-live-drift-writer`, `report-integrity`), updates the live-longer
  documents (`SKILL.md`, `actions-run-attempt-reconciliation`, `agent-profile-sync`, `forced-delegation`,
  `gate-design`, `stalled-lane-and-dispatch-delivery`, `verifying-gates-and-verdicts`, `verifying-lane-claims`),
  and drops the two stale `#1188`-split references only the tree carried (`one-builder-per-file`, `pitfalls`).

- **Proposal A — the post-merge duty**: added "Verify every merge, after the merge" to the planner SOUL and the
  live profile: read `baseRefName` (a stacked PR did not land on `main`), confirm `main` is green at the merge
  tip, measure each acceptance criterion on `main`, file a new issue naming the merged PR / merge sha / gate /
  run id and delegate to the owning lane. Never reopen a merged PR.

- **Two tests** in `test_agent_profiles.py` pin the duty in the SOUL and the "not landed on main"
  (`baseRefName != main`) discriminator in the `post-merge-verification` reference — behaviour asserted, not text.

Copy direction is live → tree because the live profile is the source of the planner's current behaviour and the
tree was the stale prefix; the one-way sync gate (issue #791) names live-longer as a finding to fix by taking the
live file into the tree, which this PR does.

## Acceptance

`make sync-agent-profile PROFILE=llgenie-planner CHECK=1` reports 55 file(s) byte-identical (exit 0),
131 `test_agent_profiles.py` cases pass, ci-scope assigns `skills,tests` with no red.
