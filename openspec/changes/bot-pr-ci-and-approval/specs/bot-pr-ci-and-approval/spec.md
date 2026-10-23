# bot-pr-ci-and-approval

## ADDED Requirements

### Requirement: A PR opened by a workflow carries its own CI run

The architecture bot SHALL create its pull request with the owner PAT (`PR_TOKEN`), never with the job token,
because a pull request created with `GITHUB_TOKEN` starts no workflows and can therefore never go green. The
issue it files SHALL keep the job token, the only credential with Issues write.

WHEN the architecture bot publishes a refresh
THEN `gh pr create` runs with the owner PAT in `GH_TOKEN`, `gh issue create` keeps the job token, and neither
value appears in argv.

#### Scenario: the PR is created with the PAT, the issue with the job token

Given `GH_TOKEN` is the job token and `PR_TOKEN` is the owner PAT
When  `publish()` files the issue and the PR
Then  the PR create carried the PAT and the issue create carried the job token
And  no token value reached the command line.

- **Test:** `tests/test_architecture_bot.py::test_the_pr_is_created_with_the_owner_pat_so_its_workflows_run`

### Requirement: This repository's own bot is an approvable author

The auto-merge job SHALL approve a review-blocked green PR whose author is this repository's own bot identity
(`BOT_LOGINS`, `…[bot]`), because that app is not the merge token's account and GitHub's self-approval rule is
therefore satisfied. A third-party author SHALL still be refused.

WHEN a green PR authored `app/github-actions` is blocked only by the required review
THEN the merge token approves it and the merge is not the admin bypass.

#### Scenario: a bot-authored PR is approved by the other identity

Given a review-blocked PR authored by `app/github-actions` and a CI run triggered by the owner
When  the job runs with review clearance enabled
Then  it posts an approving review and merges without `--admin`.

- **Test:** `tests/test_auto_merge.py::test_a_bot_authored_pr_is_approved_by_the_merge_token`

#### Scenario: a stranger is still never approved

Given a review-blocked PR from an author outside the repo's identities
When  the job runs
Then  no approving review is posted and no merge happens.

- **Test:** `tests/test_auto_merge.py::test_a_non_allowlisted_author_is_not_approved`
