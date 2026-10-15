# queued-alarm-delivery

## ADDED Requirements

### Requirement: the alarm delivers its report to a subject that exists

`--comment` MUST deliver the report to a real subject: the pull request(s) the run reports on when it
has any, otherwise ONE open issue per stuck runner label. It MUST NOT post to a workflow run id
(which 404s), and a delivery MUST be checked — a failed POST or create MUST be reported on stderr and
MUST change the exit code, so an alarm whose report did not land is never green.

WHEN a job has been queued longer than the threshold and `--comment` is given
THEN the report is visible on the run's pull request, or as a deduped issue per stuck label.

#### Scenario: the report goes on the run's pull request, never on the run id

- **Given** a stuck job in run 111, and run 111 reports on PR 42
- **When** the sweep runs with `--comment`
- **Then** exactly one comment is posted, to `/repos/{repo}/issues/42/comments`
- **And** no call to `/issues/111/comments` (a run id is not an issue number) is made
- **And** the PR is resolved from the run's head branch, because the REST run object's
  `pull_requests` is empty for a fork-PR run and `gh run view --json` has no such field
- **Test:** `tests/test_queued_run_alarm.py::test_the_report_goes_on_the_run_s_pull_request` and
  `tests/test_queued_run_alarm.py::test_the_pr_is_found_from_the_head_branch`

#### Scenario: a run no PR tracks files one deduped issue per stuck label

- **Given** a stuck job in a run that reports on no pull request (a schedule/push run)
- **When** the sweep runs with `--comment`
- **Then** ONE issue is created, naming the stuck runner label
- **And** a second sweep, with that issue already open (its marker in the body), creates nothing
- **Test:** `tests/test_queued_run_alarm.py::test_a_run_with_no_pr_files_one_deduped_issue_per_label`

#### Scenario: a delivery that fails is loud

- **Given** a stuck job whose comment POST is refused, or whose PR lookup cannot be read
- **When** the sweep runs with `--comment`
- **Then** the exit code is 3 and `DELIVERY FAILED` / `could not read the pull requests` is on stderr
- **And** a run whose PR lookup failed still files the per-label issue, so the stuck job is not lost
- **And** a read failure of the run list is still exit 2, and a stuck job with no delivery flag is 1
- **Test:** `tests/test_queued_run_alarm.py::test_a_failed_delivery_is_a_loud_exit_3` and
  `tests/test_queued_run_alarm.py::test_a_failed_pr_lookup_is_loud_and_still_reports`

### Requirement: a repeated sweep does not repeat itself, and a dry run posts nothing

The dedupe marker MUST name its subject — the run for a PR comment, the label for the fallback issue —
so the same stuck run is reported once while a NEW stuck run is still news. `--dry` MUST report what it
would post and post nothing, on any of the mutating paths (`api -X POST`, `issue create`).

WHEN the sweep runs twice over the same stuck job
THEN the second run posts nothing and still exits 1.

#### Scenario: the second sweep is silent for the same run, and dry posts nothing

- **Given** a PR comment carrying the run's marker
- **When** the sweep runs again with `--comment`
- **Then** no mutating call is made
- **And** with `--dry` no mutating call is made either, and the output says what would be delivered
- **Test:** `tests/test_queued_run_alarm.py::test_a_second_sweep_does_not_comment_again` and `tests/test_queued_run_alarm.py::test_dry_reports_what_it_would_post_and_posts_nothing`

### Requirement: the make target and the workflow state the delivery

`make queued-alarm` MUST expose the delivery (`COMMENT=1`) and the preview (`DRY=1`), the make help
line and README MUST state where the report lands, and the workflow step MUST be named for what it
does — a human reading the Actions list or `make help` must not have to read the Python to learn that
a failed delivery is an error.

WHEN the alarm's behaviour changes in the workflow, the make target or the script
THEN the make help line, the README sentence and the workflow step name change with it.

#### Scenario: the target, the help line, the README and the step name agree

- **Given** the committed `queued-alarm` target, README and `.github/workflows/queued-alarm.yml`
- **When** they are read together
- **Then** the target passes `--comment`/`--dry`, the README says the report goes to the run's PR else
  one deduped issue per stuck label, and the step names the delivery
- **Test:** `tests/test_queued_run_alarm.py` (the delivery scenarios above run through the script the
  target and the workflow both invoke) plus `make check-docs` and `make check-wiring` in `ci-unit`
