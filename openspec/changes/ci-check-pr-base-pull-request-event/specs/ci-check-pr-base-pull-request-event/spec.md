# Spec: gate `check-pr-base` to the pull_request event

## ADDED Requirements

### Requirement: the `check-pr-base` gate runs only on a pull_request

The `make check-pr-base` step in `.github/workflows/ci.yml` carries
`if: github.event_name == 'pull_request'`: on a `pull_request` run it re-fetches the
base's live `origin/main` and fails iff `git merge-base <base> <head> != <base>` (the
#845 foreign-commit protection, unchanged); on a `push` (including a push to `main`) the
step is skipped, because the pushed commit IS main's history the instant the run starts
and the gate would red on a phantom base-staleness measured by foreign commits (0).

#### Scenario: a push to main does not judge check-pr-base

Given a `push` event is running the CI workflow (including a push to `main`)
When the guard job reaches the `check-pr-base` step
Then the step is skipped
And no phantom base-staleness red is produced from the live `origin/main` fetch

#### Scenario: a pull_request still judges a branch cut from another base

Given a `pull_request` event is running the CI workflow
And the branch was cut from some base other than the live `main`
When the guard job judges check-pr-base
Then the gate re-fetches the live `main`
And it fails iff `git merge-base <base> <head> != <base>`
And a clean one-commit-ahead branch cut from `main` still passes

### Requirement: the workflow comment states the real event scope

The comment above the step describes that the gate is meaningful only on a
`pull_request`, that a push-to-main event cannot be a foreign-cut branch, and no longer
claims a push is a "tautology" while the gate still refers to a moving `origin/main`.

#### Scenario: the comment matches the step's actual event scope

Given a reader opens `.github/workflows/ci.yml` at the `check-pr-base` step
When they read the comment above the step
Then the comment states the gate runs only on a `pull_request`
And it explains the skip-on-push reason without asserting a push is a tautology
