# ci-cancel-superseded-runs

## ADDED Requirements

### Requirement: a push to a PR terminates that PR's previous run

`ci.yml` — the only workflow triggered on a pull request — MUST declare a `concurrency` group keyed
to the PR ref (`github.ref`), with `cancel-in-progress` TRUE for a `pull_request` event. A second
push to a PR branch MUST therefore cancel the run started by the push before it, instead of leaving
its jobs (the linux suite, the macOS job, the `engine-image-*` build matrix and its GHCR publish)
alive beside the new run. The group MUST be per-ref, so two different PRs never cancel each other,
and the group MUST live in the workflow the event triggers (`ci.yml`), not in a `workflow_call` file.

WHEN a commit is pushed to a branch with an open pull request
THEN the previous run for that same ref is cancelled, and its jobs are not billed against the runner queue.

#### Scenario: ci.yml names a per-ref group and supersedes its own predecessor

- **Given** `.github/workflows/ci.yml`, the only workflow triggered by `pull_request`
- **When** its `concurrency` block is read
- **Then** the group contains `github.ref` (per pull request, not one constant shared by every PR)
- **And** `cancel-in-progress` is not an unconditional literal
- **Test:** `tests/test_ci_concurrency.py::test_ci_cancels_the_run_a_push_supersedes`

#### Scenario: a pull request supersedes its predecessor, a push to main never does

- **Given** the `cancel-in-progress` expression of `ci.yml`
- **When** it is evaluated with `github.event_name` bound to `pull_request`, then to `push`
- **Then** it is true for the pull request (the previous PR run is terminated)
- **And** it is false for the push (a `main` run mid-publish to GHCR is never cancelled by its successor)
- **Test:** `tests/test_ci_concurrency.py::test_cancel_in_progress_is_true_for_a_pr_and_false_for_main`

### Requirement: the leak cannot return through a new workflow or an unconditional cancel

A workflow triggered on a pull request MUST declare a `concurrency` group, so adding a workflow to
the PR path cannot silently re-introduce the superseded-run leak. No workflow in this repo MUST set
`cancel-in-progress: true` for every event: a bot run hands up to 180 minutes of agent work to the
runner and a `main` run publishes images to GHCR, so an unconditional cancel would kill work in
flight.

WHEN a workflow that triggers on a pull request declares no concurrency group
THEN the test fails and names it, so the PR path keeps exactly one superseding rule.

#### Scenario: a pull-request workflow with no group is named, and an unconditional cancel is rejected

- **Given** every workflow file in `.github/workflows/`
- **When** each file's triggers and its `concurrency.cancel-in-progress` are read
- **Then** every workflow triggered by `pull_request` declares a group
- **And** no workflow declares the literal `cancel-in-progress: true`
- **Test:** `tests/test_ci_concurrency.py::test_every_pull_request_workflow_declares_a_group` and `tests/test_ci_concurrency.py::test_no_workflow_cancels_every_run_unconditionally`

### Requirement: the bot pipelines keep their own groups and never cancel in progress

Cancelling a superseded CI run MUST NOT change the bots' concurrency: a repair, a rebase or an
implementer run may only be superseded by its own schedule slot, never cancelled by a next tick, so
every bot workflow keeps `cancel-in-progress: false`.

WHEN the bot workflows' concurrency blocks are read
THEN each still refuses to cancel an in-progress run
THEN the CI pipeline's own group is not shared with a bot group.

#### Scenario: the bots are untouched by the CI superseding rule

- **Given** the bot workflows' concurrency blocks (`tests/test_bot_pipeline_isolation.py` holds them)
- **When** each `cancel-in-progress` is read after this change
- **Then** every bot still has `cancel-in-progress: false`
- **And** `ci.yml`'s per-ref group is its own
- **Test:** `tests/test_ci_concurrency.py::test_no_workflow_cancels_every_run_unconditionally`
