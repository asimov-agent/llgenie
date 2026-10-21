# bot-pr-token-split

## ADDED Requirements

### Requirement: Each write runs with a token that can perform it

`open_pr()` makes three writes — the claim comment, the PR, the `pr-open` marker. Each SHALL run with
the token that can perform it: the comments with the leg's issues-scoped token (`GH_TOKEN`), the PR with
the PAT (`PR_TOKEN`), and the token SHALL be applied to that child process only.

WHEN a bot PR is opened
THEN the claim comment SHALL run with `GH_TOKEN`, `pr create` with `PR_TOKEN`, and the marker with
`GH_TOKEN`, in that order — and the leg's own environment SHALL NOT be modified.

#### Scenario: every write uses its own token, in order

Given the leg carries `GH_TOKEN` (issues: write) and `PR_TOKEN` (the PAT)
When  `open_pr()` runs
Then  the comment, the PR and the marker each run with the token for their own write, in that order.

- **Test:** `tests/test_bot_pr_tokens.py::test_every_write_uses_the_token_that_can_perform_it`

#### Scenario: an unset PAT falls back to the leg's token

Given `PR_TOKEN` is not set
When  `open_pr()` runs
Then  `pr create` uses the leg's own `GH_TOKEN` rather than failing on an empty environment.

- **Test:** `tests/test_bot_pr_tokens.py::test_without_a_pat_the_legs_own_token_opens_the_pr`

### Requirement: The write that can be denied runs before the PR exists

The claim comment SHALL be posted before `pr create`, so a token without `issues: write` costs a
comment attempt and never a PR that no bot has claimed.

WHEN the claim comment is refused
THEN the command SHALL fail naming the refused write and SHALL NOT have created a PR.

#### Scenario: a denied comment costs no PR

Given a token that can open a PR but cannot comment
When  `open_pr()` runs
Then  it fails naming the denied `addComment`, and no `pr create` was invoked.

- **Test:** `tests/test_bot_pr_tokens.py::test_a_denied_comment_costs_no_pr`

### Requirement: The workflow hands the step both tokens

The issue-bot PR step SHALL carry `GH_TOKEN: ${{ github.token }}` for the comments and
`PR_TOKEN: ${{ secrets.BUMP_TOKEN }}` for the PR, so no single token has to be able to do both.

WHEN the workflow's PR step is read
THEN both variables SHALL be declared, each for the write it can perform.

#### Scenario: the step declares both tokens

Given `.github/workflows/issue-bot.yml`
When  the `Open the PR` step's env is read
Then  `GH_TOKEN` is the job's token and `PR_TOKEN` is the PAT.

- **Test:** `tests/test_bot_pr_tokens.py::test_the_workflow_hands_the_step_both_tokens`
