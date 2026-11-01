# close-implemented-on-stale-sweep

## ADDED Requirements

### Requirement: the daily branch cleanup also closes an issue a merged-to-main PR implemented

The stale-branch cleanup workflow MUST run `make issue-cleaner-apply` on its daily schedule and on
`workflow_dispatch`. The step MUST call that make target and MUST NOT call `python3 scripts/issue_cleaner.py`.
Branch deletion stays behind `APPLY`. The closer runs whether or not branches are deleted.

WHEN the stale-branch cleanup workflow is read
THEN it contains a job that runs `make issue-cleaner-apply` and grants `issues: write`.

#### Scenario: the workflow calls the make target

- **Given** `.github/workflows/stale-branch-cleanup.yml`
- **When** the close-implemented job is read
- **Then** it runs `make issue-cleaner-apply`, grants `issues: write`, and the file never calls the script directly
- **Test:** `tests/test_issue_cleaner.py::test_the_stale_branch_workflow_runs_the_closer`

### Requirement: a merge that did not land on main does not close the issue

The cleaner MUST read PRs merged into `main` and MUST ignore a PR whose `baseRefName` is another branch.

WHEN a merged PR names an open issue and its base is not main
THEN the issue is not closed.

#### Scenario: a stack-branch merge is ignored

- **Given** one PR merged into a feature branch naming #973 and one PR merged into main naming #948
- **When** the cleaner applies
- **Then** it closes #948, does not close #973, and the `gh pr list` call passes `--base main`
- **Test:** `tests/test_issue_cleaner.py::test_a_pr_merged_off_main_is_ignored`

### Requirement: a tracking vehicle and an idle-audit record stay open

A title-only match MUST NOT close the issue when more than one merged PR in the scan names that issue
by title, or when the title is an idle-audit record. An `Issue:` line on the merge commit still closes.
A `Not covered` remainder stays open.

WHEN several title-only PRs name one open issue
THEN the finding is a vehicle and the issue is not closed.

#### Scenario: two title-only PRs leave the issue open

- **Given** two merged-to-main PRs whose titles both end with `(#1079)`
- **When** the cleaner applies
- **Then** it reports a vehicle and does not close the issue
- **Test:** `tests/test_issue_cleaner.py::test_two_title_only_prs_leave_the_tracking_issue_open`

#### Scenario: an idle-audit title leaves the issue open

- **Given** a merged-to-main PR titled as an idle-audit record for #1282
- **When** the cleaner applies
- **Then** it reports an audit and does not close the issue
- **Test:** `tests/test_issue_cleaner.py::test_an_idle_audit_title_is_left_open`

#### Scenario: an Issue line still closes beside a title-only sibling

- **Given** one merged PR whose merge commit says `Issue: #256` and another that only titles #256
- **When** the cleaner applies
- **Then** it closes #256
- **Test:** `tests/test_issue_cleaner.py::test_an_issue_line_still_closes_when_another_title_names_it`
