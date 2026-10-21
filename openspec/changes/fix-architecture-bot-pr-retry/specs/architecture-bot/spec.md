# architecture-bot

## MODIFIED Requirements

### Requirement: a transient GitHub failure on the publish step is retried, then recovered

`scripts/architecture_bot.py` MUST retry `gh pr create` on a transient gateway failure (a 502, 503
or 504, or a timeout), a bounded number of times. When every attempt fails it MUST look for an
open PR whose head is the branch it pushed (`gh pr list --head <branch> --state open`) and use
that PR's URL — a create whose answer was lost may have succeeded. When no PR exists it MUST raise
an error that names the issue number and the branch the run created, so a human can finish it.

WHEN GitHub answers the PR create with a 504
THEN the run retries, and publishes the PR (or adopts the one it created) instead of failing with
an orphaned issue and branch.

#### Scenario: a transient 504 is retried
- **Given** a repository with a changed doc and a `gh` whose first two creates answer 504
- **When** `publish` runs
- **Then** it retries and returns the created PR
- **Test:** `tests/test_architecture_bot.py::test_a_transient_504_on_pr_create_is_retried`

#### Scenario: a lost create answer is recovered from the open PR
- **Given** every create answers 504 but an open PR exists on the branch
- **When** `publish` runs
- **Then** the existing PR's URL is the result
- **Test:** `tests/test_architecture_bot.py::test_a_lost_create_response_is_recovered_from_the_open_pr`

#### Scenario: a real failure names the orphans
- **Given** every create answers 504 and no PR exists on the branch
- **When** `publish` runs
- **Then** it raises naming the issue number and the branch
- **Test:** `tests/test_architecture_bot.py::test_a_real_pr_create_failure_names_the_orphans`
