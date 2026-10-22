# bot-pr-token-triggers-ci

## ADDED Requirements

### Requirement: The architecture bot's PR is opened with the owner PAT

`publish()` SHALL authenticate `gh issue create` with the job's token and `gh pr create` with a separate PR
token (`PR_TOKEN`), because a pull request opened with the job token starts no workflows. An empty PR token
SHALL fall back to the inherited token and say so on stderr.

WHEN the bot publishes a refresh
THEN the issue is filed with the job token and the PR is opened with the owner PAT.

#### Scenario: the issue and the PR use different tokens

Given a dirty doc, a job token and a separate PR token
When  `publish()` runs
Then  the `gh issue create` call carries the job token and the `gh pr create` call carries the PR token.

- **Test:** `tests/test_architecture_bot.py::test_the_pr_is_opened_with_its_own_token_so_ci_runs`

#### Scenario: a missing PR token warns instead of silently opening an unchecked PR

Given no `PR_TOKEN`
When  `publish()` opens the PR
Then  it says on stderr that the PR will trigger no CI.

- **Test:** `tests/test_architecture_bot.py::test_the_pr_is_opened_with_its_own_token_so_ci_runs`

### Requirement: The workflow supplies both tokens

The architecture bot's publish step SHALL carry `GH_TOKEN: ${{ github.token }}` for the issue and
`PR_TOKEN: ${{ secrets.BUMP_TOKEN }}` for the PR.

WHEN the workflow's publish step is read
THEN both tokens are present in its env.

#### Scenario: the publish step carries both tokens

Given `.github/workflows/architecture-bot.yml`
When  the publish step's env is read
Then  it contains the job token and the owner PAT under distinct names.

- **Test:** `tests/test_architecture_bot.py::test_the_publish_step_carries_both_tokens`
