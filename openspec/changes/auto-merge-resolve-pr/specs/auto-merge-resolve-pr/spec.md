# auto-merge-resolve-pr

## ADDED Requirements

### Requirement: A green fork run resolves its pull request

The merge workflow SHALL resolve the pull request a finished CI run belongs to even when the runs
endpoint answers 404, and SHALL find a fork head by searching for the branch rather than by a same-repo
head qualifier.

WHEN a fork pull-request CI run concludes success
THEN the merge job resolves that pull request's number and calls make auto-merge.

#### Scenario: a 404 from the runs endpoint does not kill the step

Given the runs endpoint answers 404 for the finished run
When the resolve step runs
Then it falls through to the search instead of exiting on the 404.

- **Test:** `tests/test_auto_merge.py::test_a_fork_run_is_resolved_by_search`

#### Scenario: a fork head is found by its branch

Given an open pull request whose head is a branch in the owner's fork
When the fallback runs
Then it searches by head branch and keeps the row owned by the run's head owner.

- **Test:** `tests/test_auto_merge.py::test_a_fork_run_is_resolved_by_search`
