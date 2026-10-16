# run-failure-reactor

## ADDED Requirements

### Requirement: A failed run with a pushable same-repo PR dispatches the fix-bot

A completed run whose `conclusion` is `failure` and whose `pull_requests` are non-empty SHALL be
routed to the existing `fix-bot` for that PR, reusing `scripts/fix_bot_sweep.py`'s eligibility
rules (open, non-draft, head in THIS repo, not `main`, at least one failing check, fewer than the
attempt cap). A PR whose head is a FORK SHALL NOT be dispatched (the token cannot push it). The
reactor SHALL consult the claim protocol before dispatching and SHALL claim the PR before the
dispatch.

#### Scenario: a red same-repo PR run dispatches the fix-bot

- **GIVEN** a completed failed run whose `pull_requests` names an open, non-draft, same-repo PR
- **WHEN** the reactor routes the run
- **THEN** it SHALL claim the PR and SHALL dispatch `fix-bot.yml` for that PR, and SHALL file no
  issue
- **Test:** `tests/test_run_failure_reactor.py::test_a_red_same_repo_pr_run_dispatches_the_fix_bot`

#### Scenario: a fork PR run is not dispatched

- **GIVEN** a completed failed run whose `pull_requests` names a PR whose head is in a fork
- **WHEN** the reactor routes the run
- **THEN** it SHALL NOT dispatch the fix-bot and SHALL report the fork loudly
- **Test:** `tests/test_run_failure_reactor.py::test_a_fork_pr_run_is_not_dispatched`

#### Scenario: an occupied PR is left to its holder

- **GIVEN** a red same-repo PR whose thread carries a fresh claim from another bot
- **WHEN** the reactor routes the run
- **THEN** it SHALL NOT dispatch the fix-bot and SHALL say the PR is claimed
- **Test:** `tests/test_run_failure_reactor.py::test_an_occupied_pr_is_left_to_its_holder`

### Requirement: A failed run with no pushable PR files exactly one deduped issue

A completed failed run with no pushable PR (a red `main` push, a red scheduled bot run, a red
publish job) SHALL file exactly ONE issue whose title names the workflow and the failing job, and
whose body carries the failing job, its step, and a tail of the failing log. The body SHALL carry
the marker `<!-- run-fixer: WORKFLOW/JOB@SHORTSHA -->` (SHORTSHA = first 12 chars of the head sha).
If an OPEN issue already carries that marker, the reactor SHALL file nothing. The issue SHALL be
labelled `agent:implement` so the issue-bot picks it up.

#### Scenario: a red main run with no PR becomes one issue

- **GIVEN** a completed failed run on `main` with no pull request
- **WHEN** the reactor routes the run
- **THEN** it SHALL create exactly one issue carrying the failing job, the log tail, the marker,
  and the `agent:implement` label
- **Test:** `tests/test_run_failure_reactor.py::test_a_red_main_run_with_no_pr_files_one_issue`

#### Scenario: the same head sha again files nothing

- **GIVEN** an OPEN issue already carrying the marker for this workflow/job@head-sha
- **WHEN** the reactor routes the same run again
- **THEN** it SHALL file nothing and SHALL exit 0
- **Test:** `tests/test_run_failure_reactor.py::test_the_same_head_sha_again_files_nothing`

#### Scenario: the issue body carries the failing job and the log tail

- **GIVEN** a failed run with a failing job and a failing log
- **WHEN** the reactor files the issue
- **THEN** the body SHALL name the failing job, its step, and a tail of `gh run view --log-failed`
- **Test:** `tests/test_run_failure_reactor.py::test_the_issue_body_carries_the_failing_job_and_log_tail`

### Requirement: The reactor never repairs, commits, pushes or merges

In the file-issue path the reactor SHALL NOT edit a file, create a branch, push, or merge. Its
only `gh` verbs SHALL be the reads it needs, the `issue create` that files, and the `workflow run`
that dispatches the fix-bot in Route A. The issue-bot owns implementation; the fix-bot owns PR
repair.

#### Scenario: the file path writes only an issue

- **GIVEN** a failed run with no pushable PR
- **WHEN** the reactor routes the run
- **THEN** every `gh` call it makes SHALL be a read, `issue create`, or `issue edit` — never a
  push, commit, or merge
- **Test:** `tests/test_run_failure_reactor.py::test_the_file_path_writes_only_an_issue`

### Requirement: A run the reactor cannot diagnose is loud, never silent

When a `gh` read fails or the run shape is unrecognised, the reactor SHALL report the failure to
stderr and exit non-zero — a crashed decision is never treated as "nothing to do".

#### Scenario: a crashed decision goes loud

- **GIVEN** a `gh` that fails a read the reactor needs
- **WHEN** the reactor routes the run
- **THEN** it SHALL print the failure to stderr and SHALL exit non-zero
- **Test:** `tests/test_run_failure_reactor.py::test_a_crashed_decision_goes_loud`

### Requirement: The route decision lives in code, not in a job `if:`

The workflow SHALL call the reactor through a `make` target; the decision SHALL live in
`scripts/run_failure_reactor.py`, never in a job `if:` that can silently skip (issue #107).

#### Scenario: the workflow calls the reactor through a make target

- **GIVEN** the `run-failure-reactor.yml` workflow
- **WHEN** its reactor step runs
- **THEN** it SHALL invoke `make run-failure-reactor` and SHALL carry the same token as the guard
- **Test:** `tests/test_run_failure_reactor.py::test_the_workflow_calls_the_reactor_through_a_make_target`

### Requirement: The workflow names the workflows it reacts to

`on.workflow_run` SHALL carry a `workflows:` list naming every workflow this repository owns, except
the reactor's own — GitHub REQUIRES the list and REFUSES the whole file without it, silently (a 0-job
run whose `name` is the file path and with no log). Because the trigger surface is a list of names, a
workflow file that declares `workflow_run` with no `workflows:` SHALL fail `make check-workflows`, so a
refused trigger is caught in review rather than by a silent 0-job run.

#### Scenario: a workflow_run with no workflows list fails the gate

- **GIVEN** a workflow file declaring `on.workflow_run` with no `workflows:` list
- **WHEN** the workflow gate reads it
- **THEN** it SHALL report a `workflow-run-refs` violation and SHALL exit non-zero
- **Test:** `tests/test_workflows_valid.py::test_a_workflow_run_without_a_workflows_list_is_a_violation`

#### Scenario: a workflow_run that names its workflows is accepted

- **GIVEN** a workflow file declaring `on.workflow_run` with a `workflows:` list
- **WHEN** the workflow gate reads it
- **THEN** it SHALL report no violation
- **Test:** `tests/test_workflows_valid.py::test_a_workflow_run_that_names_workflows_is_accepted`

#### Scenario: the reactor's own file passes the gate

- **GIVEN** this repository's `.github/workflows/run-failure-reactor.yml`, which names every workflow
  except itself
- **WHEN** the workflow gate reads this repository
- **THEN** it SHALL report no violation
- **Test:** `tests/test_workflows_valid.py::test_this_repository_passes_its_own_gate`
