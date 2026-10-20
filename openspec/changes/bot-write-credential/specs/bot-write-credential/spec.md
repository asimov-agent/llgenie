# bot-write-credential

## ADDED Requirements

### Requirement: A write is made with the credential that can make it

Every bot step that writes to an issue (a comment, a label) SHALL authenticate with the
repository-scoped `github.token`, and its job SHALL declare `issues: write`. Every bot step that
dispatches another workflow SHALL authenticate with `github.token`, and its job SHALL declare
`actions: write`. A step that pushes a branch SHALL keep the owner PAT, because a `github.token` push
does not re-trigger CI. No write step SHALL be handed a credential whose scopes cannot perform it.

WHEN a bot step comments on or labels an issue
THEN its `GH_TOKEN` SHALL be `${{ github.token }}` and its job SHALL grant `issues: write`.

WHEN a bot step dispatches a workflow
THEN its `GH_TOKEN` SHALL be `${{ github.token }}` and its job SHALL grant `actions: write`.

#### Scenario: the refiner's issue writes use the repository token

Given the `issue-refiner` workflow's claim, apply and report steps
When  each step's `GH_TOKEN` is read
Then  every one is `${{ github.token }}`, and the workflow grants `issues: write`

- **Test:** `tests/test_bot_write_tokens.py::test_every_issue_writing_step_uses_the_repo_scoped_token`

#### Scenario: every writing step has the permission it uses

Given the issue-writing and workflow-dispatching steps of every bot workflow
When  each job's effective permissions are resolved
Then  each grants the write the step performs (`issues: write` or `actions: write`)

- **Test:** `tests/test_bot_write_tokens.py::test_every_writing_step_has_the_permission_it_uses`

#### Scenario: a pushing job still carries the owner PAT

Given a job whose step runs `git push`
When  the step env, the job env and the job's checkout token are read
Then  the owner PAT backs the push, because a `github.token` push never re-triggers CI

- **Test:** `tests/test_bot_write_tokens.py::test_a_push_still_uses_the_owner_pat`
