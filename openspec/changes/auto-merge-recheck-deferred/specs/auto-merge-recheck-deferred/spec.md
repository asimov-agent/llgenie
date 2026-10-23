# auto-merge-recheck-deferred

## ADDED Requirements

### Requirement: A deferred PR is re-evaluated against its current head

The auto-merge gate SHALL provide a recheck sweep that re-runs the SAME decision for every open PR whose own
deferral marker matches its current head SHA, so a blocker that clears without a push is acted on. A PR with no
marker, or with a marker for a different head, SHALL be left alone.

WHEN the recheck sweep runs
THEN a PR carrying `<!-- auto-merge: deferred <current head> -->` is re-evaluated exactly as a fresh run would.

#### Scenario: the cleared blocker is finished without a push

Given a green, clean PR carrying the deferral marker for its current head
When  the recheck sweep runs
Then  it approves/merges through the one decision, and the merge carries no `--admin`.

- **Test:** `tests/test_auto_merge.py::test_a_deferred_pr_is_retried_and_merged_when_the_blocker_cleared`

#### Scenario: a marker for an older head is not a retry

Given a deferral marker naming a head the PR no longer has
When  the sweep runs
Then  nothing is approved or merged for it.

- **Test:** `tests/test_auto_merge.py::test_a_marker_for_another_head_is_not_retried`

#### Scenario: a PR the gate never deferred is untouched

Given an open PR with no deferral marker
When  the sweep runs
Then  it is not merged, approved or commented on.

- **Test:** `tests/test_auto_merge.py::test_a_pr_without_a_deferral_marker_is_not_touched`

### Requirement: The sweep is scheduled, bounded and runnable by hand

`auto-merge.yml` SHALL run the recheck on a schedule (every 30 minutes), with the
owner PAT and the optional `APPROVER_TOKEN`; the sweep SHALL process at most `MAX` PRs per run and print one
line per PR.

WHEN the schedule fires
THEN the recheck job runs `make auto-merge-recheck REPO=<repo>` in the base repository with its secrets.

#### Scenario: the workflow carries the schedule and the job

Given `.github/workflows/auto-merge.yml`
When  its triggers and jobs are read
Then  it declares a `schedule` and a `recheck` job that runs the make target, and the `merge` job stays
`workflow_run`-only.

- **Test:** `tests/test_auto_merge.py::test_the_recheck_is_scheduled_and_runs_the_make_target`
