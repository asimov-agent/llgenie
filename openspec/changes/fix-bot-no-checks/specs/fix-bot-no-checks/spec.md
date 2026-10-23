# fix-bot-no-checks

## ADDED Requirements

### Requirement: A branch with no checks is not a failing PR

The fix-bot's sweep SHALL treat `gh pr checks` answering "no checks reported on the '<branch>' branch" as
"this PR has nothing red", not as a failed call. Any other `gh` failure SHALL still abort the sweep loudly.

WHEN the sweep reads a PR whose branch has no checks at all
THEN it skips that PR, continues to the next one, and exits 0.

#### Scenario: the check-less PR is skipped and the sweep finishes

Given one open PR whose branch has no checks (`gh pr checks` exits non-zero with "no checks reported")
When  the sweep runs
Then  it exits 0, reports no failing check for that PR, and finishes with "nothing to fix among 1 open PR(s)".

- **Test:** `tests/test_fix_bot_sweep.py::test_a_pr_with_no_checks_does_not_kill_the_sweep`

#### Scenario: a real API failure still aborts

Given `gh pr checks` failing for any other reason
When  the sweep runs
Then  the run is non-zero and the `gh` error is printed, unchanged.

- **Test:** `tests/test_fix_bot_sweep.py::test_a_pr_with_no_checks_does_not_kill_the_sweep` (the stub only
  synthesises the "no checks reported" failure; every other non-zero answer still raises).
