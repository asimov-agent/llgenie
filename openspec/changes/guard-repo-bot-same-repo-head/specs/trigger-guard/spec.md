# trigger-guard

## ADDED Requirements

### Requirement: The repository's own bot is admitted only on a same-repo head

The trigger guard SHALL admit `github-actions[bot]` without a collaborator permission read **only** when
the run's head repository is this repository (`github.event.pull_request.head.repo.full_name` equals
`github.repository`), SHALL pass that value to the guard as `HEAD_REPO`, and SHALL keep refusing every
other actor that is neither the repository owner nor a collaborator with `admin|maintain|write`. A bot
acting on a foreign head, or on a non-PR event where no head repository exists, SHALL be refused. The
guard body SHALL stay byte-identical in every workflow that carries it.

WHEN a workflow run reaches the trigger guard
THEN the repository's own bot is admitted on a same-repo head and refused everywhere else,
AND  the owner and write collaborators keep passing, and every other login is refused.

#### Scenario: the bot passes on a same-repo head

Given the run's actor is `github-actions[bot]` and its head repository is this repository
When  the guard runs
Then  it admits the run and says the head is same-repo.

- **Test:** `tests/test_workflow_guards.py::test_the_repository_bot_passes_on_a_same_repo_head`

#### Scenario: the bot is refused on a foreign head

Given the run's actor is `github-actions[bot]` and its head repository is someone else's fork
When  the guard runs
Then  it refuses the run.

- **Test:** `tests/test_workflow_guards.py::test_the_bot_is_refused_on_a_foreign_head`

#### Scenario: the bot is refused when there is no head repository

Given the run's actor is `github-actions[bot]` and the event carries no head repository
When  the guard runs
Then  it refuses the run, never admitting it through an empty comparison.

- **Test:** `tests/test_workflow_guards.py::test_the_bot_is_refused_when_no_head_repo_exists`

#### Scenario: a stranger stays refused on a same-repo head

Given a login with no collaborator permission and a head repository that is this repository
When  the guard runs
Then  it refuses the run.

- **Test:** `tests/test_workflow_guards.py::test_a_stranger_is_refused_even_on_a_same_repo_head`

#### Scenario: the owner and a write collaborator still pass

Given the repository owner as the actor, or a collaborator whose permission is `write`
When  the guard runs
Then  the run is admitted.

- **Test:** `tests/test_workflow_guards.py::test_the_owner_and_a_write_collaborator_still_pass`

#### Scenario: every guard site passes the head repository

Given every workflow that carries the guard
When  its guard step's environment is read
Then  it declares `HEAD_REPO`.

- **Test:** `tests/test_workflow_guards.py::test_every_guard_site_declares_the_head_repo`

#### Scenario: the guard body stays one body

Given every workflow that carries the guard
When  the guard steps are compared
Then  they are byte-identical, so a rule fixed once cannot miss another site.

- **Test:** `tests/test_workflow_guards.py::test_every_guard_step_is_byte_identical`
