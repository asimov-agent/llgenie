# ci-verdict — a run is held to the scope decision it published (issue #1111)

## ADDED Requirements

### Requirement: A finished run is held to its published scope decision

A run's check-runs report conclusions; they do not say whether a missing job was ALLOWED to be
missing. The decision that selected the jobs MUST therefore be published as data, and a finished run
MUST be compared against it, so that "nothing ran" and "nothing needed to run" stop producing the
same row.

WHEN  a CI run finishes, whatever its conclusion
THEN  its job rows are read against the `ci-scope-decision` artifact it published
AND   every job the decision selected MUST report a conclusion that is a verdict, and every skip the
      decision made is counted as such.

#### Scenario: a cancelled fan-out published no decision

Given a CI run that was cancelled before its decision was published,
When   its jobs are put to the verdict,
Then   the verdict is `none`, no skipped or cancelled row is counted as a legitimate skip, and the
       summary reports `verdict=none … 0 failures is not a verdict`.
- **Test:** `tests/test_ci_verdict.py::test_a_cancelled_fan_out_with_no_decision_is_never_green`

#### Scenario: a selected job never reported

Given a published decision that selected `linux/unit` and a run whose `linux` caller was skipped so no
`linux / unit` row exists,
When   the run is held to that decision,
Then   the verdict names `linux/unit ABSENT` and is not green.
- **Test:** `tests/test_ci_verdict.py::test_a_selected_job_that_never_reported_reds_the_verdict`

#### Scenario: a job the decision selected reports cancelled

Given a published decision that selected `ci-images` and a run where it reported `cancelled`,
When   the run is held to that decision,
Then   it is counted as `no_verdict`, never as `skipped-by-decision`.
- **Test:** `tests/test_ci_verdict.py::test_a_cancelled_row_the_decision_selected_is_unaccounted_not_skipped_by_decision`

#### Scenario: a skip the decision made stays green

Given a `tests/**`-class decision that does not select `scanner-images`, `install`, `agents-read`,
`openspec` or `cpu-health`, and a run where those are skipped or absent,
When   the run is held to that decision,
Then   the verdict is green and every such skip is counted as `skipped-by-decision`.
- **Test:** `tests/test_ci_verdict.py::test_a_skip_the_decision_made_is_green_and_counted`

### Requirement: The verdict is visible where the question is asked

A `workflow_run` run creates no check-run of its own on the commit (measured on `0bd5ac6e`), so a
verdict that only reds its own workflow is invisible to the reader this exists for. The verdict MUST be
posted as a `ci-verdict` check-run on the head.

WHEN  the verdict reaches an answer
THEN  a `ci-verdict` check-run is posted on the run's head with `failure` for `none`/`red` and
      `success` only for a green verdict.

#### Scenario: a run with no verdict posts a failure check-run

Given the measured cancelled fan-out of run 41134761297 and no decision artifact,
When   `make ci-verdict` runs with `CHECK_RUN_OUT` set,
Then   it exits 1, the payload's conclusion is `failure`, and the payload's name is `ci-verdict`.
- **Test:** `tests/test_ci_verdict.py::test_the_cli_exits_one_and_writes_a_failure_check_run_for_a_cancelled_run`

#### Scenario: a decided skip posts a success check-run that names the skip

Given a `tests/**`-class decision and a run whose unselected jobs were skipped,
When   `make ci-verdict` runs with `CHECK_RUN_OUT` set,
Then   it exits 0 and the payload's summary contains `skipped-by-decision=5`.
- **Test:** `tests/test_ci_verdict.py::test_the_cli_exits_zero_and_writes_a_success_check_run_for_a_decided_skip`

### Requirement: A superseded head is neutral, never a pass

`ci.yml` cancels the run above it on every push, so a cancelled run that a LATER run of the same
workflow on the same branch already replaced is owed nothing — but it still MUST NOT read as a pass.

WHEN  the run being judged has a later run of the same workflow on the same branch
THEN  the verdict is reported `neutral` and the job exits 0
AND   the check-run conclusion is `neutral`, never `success`.

#### Scenario: a cancelled run with a later successor

Given a cancelled run with no decision artifact and a later run of the same workflow on the branch,
When   the verdict reads the run through the API (a stub `gh` in the test),
Then   it exits 0, prints `SUPERSEDED by run <id>`, and posts a `neutral` check-run.
- **Test:** `tests/test_ci_verdict.py::test_a_cancelled_run_a_later_run_superseded_is_neutral_not_a_pass`

#### Scenario: a cancelled run with no successor is red

Given the same run and no later run of its workflow,
When   the verdict reads it,
Then   it exits 1 with `verdict=none` and posts a `failure` check-run.
- **Test:** `tests/test_ci_verdict.py::test_a_cancelled_run_with_no_successor_is_red_even_through_the_api`

### Requirement: An unreadable decision is an error, never "nobody decided"

A transport failure MUST NOT be dressed up as a `none` verdict, because `none` is an answer about the
run while a download failure is an answer about the network.

WHEN  the decision artifact exists but cannot be read
THEN  the verdict exits 2 and prints `could not reach a verdict`.

#### Scenario: the artifact is listed but the download fails

Given a run whose artifact listing names `ci-scope-decision` and a `gh` that fails the download,
When   the verdict runs,
Then   it exits 2 and never writes a verdict.
- **Test:** `tests/test_ci_verdict.py::test_an_artifact_that_exists_but_cannot_be_downloaded_is_an_error_not_a_verdict`

### Requirement: The decision is published by the run it judges, and nothing is skipped by a condition

The decision MUST be published on every CI run (so a cancelled run leaves "no list" rather than an
implicit "empty list"), and no job-level `if:` may be added to achieve it.

WHEN  `ci.yml`'s `guard` job runs
THEN  it writes the decision through `make ci-scope` and uploads `ci-scope-decision` with
      `if-no-files-found: error`
AND   no job or step gains a condition that skips it.

#### Scenario: ci.yml publishes the artifact the verdict reads

Given `ci.yml` at this change,
When   its `guard` steps are read,
Then   `make ci-scope BASE=` / `ALL=1` and the `ci-scope-decision` upload with `if-no-files-found:
       error` are present, and `test_no_ci_step_or_job_is_skipped` still passes.
- **Test:** `tests/test_ci_verdict.py::test_ci_yml_publishes_the_decision_artifact_the_verdict_reads`
  and `tests/test_ci_images.py::test_no_ci_step_or_job_is_skipped`

#### Scenario: the consumer is watched

Given `ci-verdict.yml`,
When   its triggers, permissions and the reactor roster are read,
Then   it fires on `CI`/`completed`, holds `checks: write`, posts the payload, and is named in
       `run-failure-reactor.yml`'s roster.
- **Test:** `tests/test_ci_verdict.py::test_the_verdict_workflow_watches_ci_and_posts_the_check_run`
  and `tests/test_ci_verdict.py::test_the_roster_names_this_workflow_so_a_red_verdict_is_routed`
