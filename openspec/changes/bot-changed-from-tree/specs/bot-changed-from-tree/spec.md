# bot-changed-from-tree

## ADDED Requirements

### Requirement: The implementation is measured from the working tree

Whether a bot run implemented anything SHALL be decided from the working tree after the implement step
— `git status --porcelain --untracked-files=all`, minus the bot's own run inputs — and never from the
agent's exit status. A run that changed nothing SHALL push nothing and fail the job, naming the issue.

WHEN the implement step returns and the tree is inspected
THEN `make issue-bot-changed` SHALL print `changed=true` only when a file that is not a run input
(`issue.md`, `triage.md`, `refine-in.md`, `refine.md`, `comment.md`) differs from the checkout, and the
job SHALL fail loudly when the verdict was `implement` and it printed `false`.

#### Scenario: a run that only wrote its verdict changed nothing

Given a repository where the implement step wrote `triage.md` and touched no tracked file
When  `make issue-bot-changed` runs
Then  it prints `changed=false`, so the push step is skipped and the loud failure fires — the verdict
      can never become the implementation.

- **Test:** `tests/test_issue_implementer.py::test_changed_is_false_when_only_a_run_input_appeared`

#### Scenario: a real change is changed=true

Given a repository with one edited tracked file and one new source file
When  `make issue-bot-changed` runs
Then  it prints `changed=true` and the push step proceeds exactly as before.

- **Test:** `tests/test_issue_implementer.py::test_changed_is_true_for_a_real_edit`

#### Scenario: a tree that cannot be read is a failure, not a green run

Given a directory that is not a git repository, or a `git` that exits non-zero
When  `make issue-bot-changed` runs
Then  it exits 2 with a message naming what it could not read, so an unreadable tree is never mistaken
      for "changed=true" or "changed=false".

- **Test:** `tests/test_issue_implementer.py::test_changed_fails_loudly_outside_a_git_tree`

### Requirement: The workflow gates the push and the failure on the tree

The issue-bot workflow SHALL call `make issue-bot-changed` and SHALL gate both the push step and the
"fail loudly" step on its result; it SHALL NOT set an `implemented` flag from `make implement-issue`'s
exit code alone.

WHEN the workflow is read
THEN the push step SHALL require `changed == 'true'`, the loud-failure step SHALL fire when the change
is missing or the agent failed, and no step SHALL derive the outcome from `rc` alone.

#### Scenario: the workflow runs the target and gates on it

Given `.github/workflows/issue-bot.yml`
When  the implement, detect, push and failure steps are read
Then  a detect step runs `make issue-bot-changed`, the push requires its output, the failure step covers
      `rc != 0` or a missing change, and no `implemented=` is written from an exit code.

- **Test:** `tests/test_issue_implementer.py::test_the_workflow_gates_push_and_failure_on_the_tree`
