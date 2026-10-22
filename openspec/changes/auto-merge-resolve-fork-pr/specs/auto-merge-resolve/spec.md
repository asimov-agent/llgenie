# auto-merge-resolve

## ADDED Requirements

### Requirement: A finished run is resolved to its PR, and only a number is a number

The auto-merge gate SHALL resolve the pull request a finished CI run belongs to from the run object
first and from the head branch (scoped to the head repository's owner) second, and SHALL treat only a
digits-only value as a pull-request number — a 404 body, an error line or an empty answer is no answer
and SHALL fall through to the next source. When nothing resolves, the gate SHALL fail loudly, naming the
run and the head, and SHALL NOT write a value. A resolved number SHALL be written to `$GITHUB_OUTPUT`
as the single line `number=<n>`. The gate SHALL run through `make auto-merge-resolve`, so the workflow
runs the tested code path and not its own copy of the logic.

WHEN a finished CI run is mapped back to its pull request
THEN the resolved number comes from the run object or the owner-scoped head search,
AND  a non-numeric answer from the runs endpoint is never mistaken for a number.

#### Scenario: a fork run's 404 falls through to the head search

Given a fork pull_request run, whose runs endpoint answers 404 with an error body on stdout
When  the gate resolves the run
Then  the error body is "no answer", and the PR is found through the owner-scoped head search.

- **Test:** `tests/test_resolve_run_pr.py::test_a_404_from_the_runs_endpoint_falls_through_to_the_fork_head`

#### Scenario: the run object is used when it answers

Given a run whose `pull_requests` array carries the PR number
When  the gate resolves the run
Then  the number comes from the run object and no head search is made.

- **Test:** `tests/test_resolve_run_pr.py::test_the_run_object_is_used_when_it_answers`

#### Scenario: the head search is scoped to the head owner

Given a fork run that only the head search can resolve
When  the gate searches for the open PR
Then  the search filters on the head branch AND the head repository's owner.

- **Test:** `tests/test_resolve_run_pr.py::test_the_fork_search_is_scoped_to_the_head_owner`

#### Scenario: nothing resolving is loud

Given a run that neither source can resolve
When  the gate resolves it
Then  the gate exits non-zero naming the run and the head, and writes no value.

- **Test:** `tests/test_resolve_run_pr.py::test_nothing_resolving_is_loud_and_writes_no_output`

#### Scenario: the output is exactly one number line

Given a resolved PR and a `$GITHUB_OUTPUT` file
When  the gate writes its result
Then  the file holds exactly `number=<n>` on one line, never a multi-line body.

- **Test:** `tests/test_resolve_run_pr.py::test_the_output_file_gets_one_number_line`

#### Scenario: the workflow runs the make target

Given the real `auto-merge.yml`
When  its resolution step is read
Then  it calls `make auto-merge-resolve` and contains no inline `gh` request of its own.

- **Test:** `tests/test_resolve_run_pr.py::test_the_workflow_resolves_the_pr_through_the_make_target`
