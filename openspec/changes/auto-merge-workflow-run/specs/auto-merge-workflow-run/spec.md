# auto-merge-workflow-run

## ADDED Requirements

### Requirement: The merge executes where the owner PAT exists

The merge SHALL run in a `workflow_run` workflow triggered by the `CI` workflow's completion, executing in the
base repository with `secrets.BUMP_TOKEN`, and SHALL act only on a `pull_request` run that concluded
`success`. It SHALL resolve the pull request from the finished run and SHALL merge through `make auto-merge`,
the one implementation.

WHEN a CI run for a pull-request head finishes green
THEN the merge workflow runs in the base repo with the PAT, resolves that PR, and merges it when the PR is
mergeable and clean.

#### Scenario: a green fork run reaches the merge with a real token

Given a fork PR whose CI run concluded `success`
When  the merge workflow runs
Then  it executes with `secrets.BUMP_TOKEN`, resolves the PR number from the run, and calls `make auto-merge`.

- **Test:** `tests/test_auto_merge.py::test_the_merge_is_a_workflow_run_on_ci`

#### Scenario: a push run or a red run never merges

Given a CI run that was a push to main, or one that failed
When  the merge workflow is evaluated
Then  its job is skipped — there is no pull request, or the code is not green.

- **Test:** `tests/test_auto_merge.py::test_only_a_successful_ci_run_reaches_the_merge`

#### Scenario: ci.yml no longer carries the job

Given `ci.yml`
When  its jobs are read
Then  there is no `auto-merge` job, and a comment names `auto-merge.yml` as where the merge went.

- **Test:** `tests/test_auto_merge.py::test_ci_has_no_auto_merge_job_any_more`

### Requirement: Only the owner, a write collaborator, or the bot is merged

The merge SHALL refuse a pull request whose author is not the repository owner, a collaborator with write (or
more), or the bot — the same gate `ci.yml`'s `guard` job applies to a run. A bot-authored pull request SHALL
be authorised by the actor who triggered the CI run, because the bot's own permission endpoint answers
nothing useful.

WHEN a green, clean pull request is opened by someone who is none of those
THEN the merge defers, posts the reason, and never calls `gh pr merge`.

#### Scenario: a write collaborator and a bot PR merge, a stranger does not

Given a green, clean PR opened by a collaborator with write, and one opened by the bot whose CI run was
triggered by the owner, and one opened by a stranger even from the trusted fork
When  the merge runs
Then  the first two merge and the stranger's is deferred without a merge.

- **Test:** `tests/test_auto_merge.py::test_a_write_collaborator_a_bot_and_the_owner_may_merge_a_stranger_may_not`

### Requirement: A run that cannot merge fails loudly

When no token is available, the merge SHALL fail (exit 2) naming the defect rather than deferring with exit 0,
and the workflow's first step SHALL fail when `secrets.BUMP_TOKEN` is empty.

WHEN the token is empty
THEN the run is red and says so, and no deferral comment is posted.

#### Scenario: an empty PAT is a red run

Given the merge workflow and an empty `secrets.BUMP_TOKEN`
When  the job starts
Then  the first step exits non-zero before any checkout or merge.

- **Test:** `tests/test_auto_merge.py::test_an_empty_pat_fails_the_workflow_loudly`

#### Scenario: the CLI refuses to decide without a token

Given neither `GH_TOKEN` nor `GITHUB_TOKEN` is set
When  the CLI is invoked
Then  it exits 2 and prints that it cannot merge.

- **Test:** `tests/test_auto_merge.py::test_no_token_is_a_loud_failure_not_a_deferral`

### Requirement: Only this repo's own heads are merged

The merge decision SHALL defer a pull request whose head repository is neither the base repository nor
`andyholst/llgenie`, because a `workflow_run` workflow fires for any fork.

WHEN the head belongs to a third-party fork
THEN the decision defers, naming the head, and no merge or approval happens.

#### Scenario: a stranger's fork is deferred

Given a green, clean PR whose head repository is `someone-else/llgenie`
When  the decision runs
Then  it defers with a reason naming a third-party fork.

- **Test:** `tests/test_auto_merge.py::test_a_third_party_fork_head_is_never_merged`
