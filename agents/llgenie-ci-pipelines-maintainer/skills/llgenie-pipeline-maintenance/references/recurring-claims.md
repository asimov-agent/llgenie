# Recurring claims that come back — sweep before you take them

## #1407 (un-owned linux/unit red) — already shipped by this lane

PR **#1416** merged `450e37e0` (2026-11-01 17:42:47Z) closed #1407 as COMPLETED
(closedAt 17:42:49Z, closedByPullRequestsReferences = [#1416]).

The fix: `.github/workflows/registry-liveness.yml` — cron minutes 11/29/47 → 35/49/1
(those were owned by search-smoke/rebase-bot/architecture-bot, #275/#301) and removed
its unroster'd actor-guard job (a non-dispatchable workflow must not carry a 26th guard
site; `test_every_guard_step_is_byte_identical` pins exactly len(_dispatchable())+1 = 25).
Acceptance proof: green run **41331643817** (linux/unit job + `make ci-unit` step SUCCESS,
2805 passed), #1123 change-note pair.

**The planner re-routes #1407 as a "new routed issue" / "first in" repeatedly — even
after it is CLOSED by my own PR.** Each time it arrives, sweep-before-claim wins:

```bash
gh issue view 1407 --json state,stateReason,closedAt,closedByPullRequestsReferences
gh pr view 1416 --json state,mergedAt,mergeCommit,title
# current main head + its live CI, not a historical sha
git ls-remote upstream main
gh run list -R asimov-agent/llgenie --branch main --limit 5
```

A closed-by-own-PR issue is a **duplicate-vehicle trap (#824)**, never live work.
Do NOT create the branch, PR, or claim. Report the measured closure to the inbox and
offer: if you mean a *different* still-red step (test-unit vs skills-validate vs
check-registry vs check-strata-models vs check-engine-params), re-measure the current-head
CI and file a fresh six-section issue.

## General rule

Before claiming anything the inbox routes, verify (a) the issue is actually OPEN, and
(b) the red it tracks is actually live at the current canonical head. Both can be stale.
An issue that is CLOSED/COMPLETED because your own prior PR shipped is the common
distractor — the inbox's routing comments lag real merges.
