# rebase-behind-despite-comment

## ADDED Requirements

### Requirement: A plain comment never holds a PR that is behind main

The rebase sweep SHALL rebase a pull request that is `BEHIND` or `DIRTY` against `main` even when the pull request carries a recent comment that is not a claim. A comment SHALL hold the subject only when it carries a `bot-claim` marker from another bot, or a `bot-done` marker whose outcome still occupies the subject.

WHEN a pull request is behind main and its newest comment is a status note with no claim marker
THEN the sweep selects it for rebase.

#### Scenario: a status comment does not stop the rebase

Given a pull request that is BEHIND against main
And its newest comment is a person's note with no bot-claim marker
When the sweep runs
Then the pull request is selected for rebase.

- **Test:** `tests/test_rebase_bot_sweep.py::test_a_plain_comment_does_not_hold_a_pr_that_is_behind`

#### Scenario: a real claim still holds

Given a pull request that is DIRTY against main
And another bot posted a fresh bot-claim marker
When the sweep runs
Then the pull request is passed over and the reason names the claim.

- **Test:** `tests/test_rebase_bot_sweep.py::test_a_pr_the_other_bot_has_claimed_is_left_alone`
