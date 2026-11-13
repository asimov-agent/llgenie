# Arms gate queue semantics — issue #2378

## What was verified

- Measured at main `2f6574ea8`: the old `scripts/check_arms.py` classed **every open lane as a finding**
  while checks were still running (4/4 open PRs flagged locally; scheduled arms run 43181777316, job
  129043889459, is the tracker's red). The rule-16 reading demanded `autoMergeRequest` on every mergeable,
  non-draft, main-based PR — impossible for the agent lane, which AGENTS.md forbids from `gh pr merge`
  (no `--auto` either); the lane's queue entry is the CI auto-merge job's `mergeStateStatus CLEAN`.
- Fix tree: `make check-arms` rc=0 against the live board — 4/4 PRs named `red`, `in CI`, or `in-flight`,
  0 findings (the negative control against the old script's 4/4 at the same head).
- `tests/test_arms.py` battery green; negative controls (mid-CI, empty rollup, CLEAN-queued,
  review-chain-in-flight, red-rollup) all fail on the pre-fix tree by construction.
- `make check-workflows`, `make check-wiring`, `make lint`,
  `make openspec-validate NAME=arms-gate-queue-semantics` rc=0.

## Key decisions

- FINISHED now means check-terminal + GREEN; QUEUED means `autoMergeRequest != null` OR
  `mergeStateStatus == CLEAN`; REVIEW_REQUIRED/CHANGES_REQUESTED is unfinished work, not a finding.
- Rule 16 keeps its teeth on the stuck class: green + review chain landed + neither armed nor CLEAN-queued
  (BLOCKED-after-approval or BEHIND) is still a named finding, rc 1.
- `arms.yml` kept its trigger surface, permissions, and name untouched — only header comments and the step
  name carry the new semantics; the workflow name is a long-lived dedupe identity.
- Post-merge follow-up (not a tasks.md item): dispatch `arms.yml` on main and record the green job id +
  0-finding verdict here and in issue #2378.

## Current status

Issue #2378, branch `feat/arms-gate-queue-semantics`; the PR carries the ticked acceptance mirrors and
closes the issue on merge.
