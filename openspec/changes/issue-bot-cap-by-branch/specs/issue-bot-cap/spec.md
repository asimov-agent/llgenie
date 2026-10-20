# issue-bot-cap

## ADDED Requirements

### Requirement: The cap counts the PRs the issue-bot itself opened

The dispatcher's cap numerator SHALL count a pull request only when it was created in the current UTC day
AND it is the issue-bot's own — identified by the branch shape `dispatch` creates
(`agent/issue-<n>-<slug>`), never by the `github-actions[bot]` login the bot does not use. A human's pull
request SHALL never be counted.

WHEN the cap numerator is computed
THEN only today's `agent/issue-*` pull requests count, whatever author opened them.

#### Scenario: the numerator is the bot's own PRs

Given three pull requests on the dispatcher's `agent/issue-` branches, created today
When  the numerator is computed
Then  it is 3, and the query reads the repository's PRs by branch, author and creation date

- **Test:** `tests/test_issue_implementer.py::test_count_prs_opened_today_matches_the_cap_numerator`

#### Scenario: a human's PR and yesterday's PR do not count

Given the same pull requests
When  the numerator is computed for the next day
Then  it is 0

- **Test:** `tests/test_issue_implementer.py::test_count_ignores_a_humans_pr_and_a_pr_from_another_day`

#### Scenario: the cap still stops the run

Given three of the bot's pull requests already opened today
When  the dispatcher runs
Then  it reports `action=cap` and starts no work

- **Test:** `tests/test_issue_implementer.py` (the existing cap test, unchanged)
