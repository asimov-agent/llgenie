# 2026-11-27 — a forced dispatch at the daily cap fails loudly (#3116)

`issue-bot.yml` accepts an owner-only `workflow_dispatch` input `issue_number` that pins
the run to one issue (`FORCE_ISSUE`). At origin/main `4b1fcb2b`, `dispatch()` in
`scripts/issue_implementer.py` checked the 3/day cap at lines 390–394 before it ever read
`force_issue` at line 396. A forced run after the cap was consumed returned
`{"action": "cap", "count": 3, "issue": None}` and the workflow completed `success` with no
branch, no PR and no comment — measured on #3044, run `46072901981`, log line
`[issue-implementer] cap reached: 3/3 today, next issue tomorrow` at 21:51:03Z. Diagnosis
is recorded on #3044 comment `7228860903`.

## Decision

Contract **(b)**: the cap wins, but a forced call at the cap is never silently dropped.
`dispatch()` now exits nonzero with an `::error::` naming both the forced issue and the cap;
the workflow's existing rc check fails that job, so `success` can no longer mean "no vehicle".
The automatic path's `action=cap` at 3/3 is byte-for-byte unchanged.

Contract (a) (forced issue bypasses the cap) was considered and rejected for this vehicle:
acceptance criterion 4 needs a real `issue-bot.yml` run for a forced issue at the cap, and
under (a) that run would implement the issue and open a second branch/PR. The owner's
"one PR, no second branch" constraint forbids that. The switch is recorded on #3116
comment `7228976499`.

## Verification

- New seam test `test_forced_issue_at_the_cap_fails_loudly_naming_issue_and_cap` asserts
  `SystemExit != 0` plus `::error::forced issue #99 was NOT dispatched` and
  `daily cap is reached (3/3)`, and that no issue view/list/comment, PR or `issue.md` was made.
- Negative control: production change stashed, new test run against the old tree →
  `Failed: DID NOT RAISE <class 'SystemExit'>`, rc=1. Restored → the new test plus the unchanged
  automatic-cap test `2 passed`, rc=0.
- `test_cap_reached_at_three_exits_zero_and_changes_nothing` remains the automatic-path proof:
  `action=cap`, `issue=None`, `cap reached: 3/3`, no issue query or comment, no `issue.md`.
- Workflow text at `.github/workflows/issue-bot.yml` documents the chosen contract beside the
  `cap`/`none` → `dispatch=false` decision, so the gate's own text states what it enforces.

Related: #3044 (the blocked issue that exposed the silent success), #312 (a crashed decision
must not be treated as nothing-to-do — the same "success with no action" class).

Implements #3116. Vehicle: `fix/3116-forced-dispatch-cap` (one PR, opened from this branch;
the PR number is stamped in the PR body and issue thread, not guessed here).
