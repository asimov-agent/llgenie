# issue-cleaner

## ADDED Requirements

### Requirement: a merged PR's implemented issue is derived from evidence, never assumed

The cleaner MUST resolve the issue a merged PR implements from the PR's own record, strongest signal first:
`closingIssuesReferences` (non-empty means the issue closed at merge), then the merge commit's `Issue: #<n>`
line, then the title's trailing `(#<n>)`. A PR that names no issue MUST be ignored.

WHEN a merged PR is read
THEN it yields at most one `(issue, evidence)` pair, and `None` when its body already closed its issue or it
names none.

#### Scenario: the merge commit's Issue line is the implemented issue

- **Given** a merged PR whose merge commit message contains `Issue: #256`
- **When** the cleaner reads it
- **Then** the implemented issue is 256 and the evidence names the merge commit's line
- **Test:** `tests/test_issue_cleaner.py::test_implemented_issue_prefers_the_merge_commit_then_the_title`

#### Scenario: a body that closed its issue is not this bot's business

- **Given** a merged PR whose `closingIssuesReferences` contains the issue
- **When** the cleaner reads it
- **Then** it yields no finding
- **Test:** `tests/test_issue_cleaner.py::test_implemented_issue_is_none_when_the_body_closed_it`

### Requirement: a tracked remainder is left open

A still-open issue the PR names under its own `Not covered` section MUST be reported as a `remainder` and
MUST NOT be closed. The section runs from its heading to the next heading, so a remainder list cannot
swallow an unrelated later section.

WHEN a merged PR implemented an issue that is still open
THEN it is a `close` finding, unless the PR's `Not covered` section names that issue, in which case it is a
`remainder` finding and the issue stays open.

#### Scenario: an issue named under Not covered is a remainder

- **Given** a merged PR whose `Not covered` names #339 and whose implemented issue is #339
- **When** the cleaner decides
- **Then** the finding is a `remainder`, its reason says the issue is left open, and no close is issued
- **Test:** `tests/test_issue_cleaner.py::test_a_remainder_is_reported_and_never_closed`

#### Scenario: an issue the PR implemented and did not disclaim is closed

- **Given** a merged PR that implemented still-open #256 and named no remainder #256
- **When** the cleaner runs with `--apply`
- **Then** it posts an evidence comment on #256 and closes it as completed
- **Test:** `tests/test_issue_cleaner.py::test_apply_posts_the_evidence_and_closes`

### Requirement: the scan mutates nothing

`--dry` MUST print every finding and mutate nothing. The bot MUST announce itself on the issue through the
shared claim marker (#279) before it comments or closes.

WHEN the cleaner runs in its scan mode
THEN no comment is posted and no issue is closed.

#### Scenario: dry run closes nothing

- **Given** one stale-open finding
- **When** the cleaner runs with `--dry`
- **Then** it prints the finding and `gh` receives neither `issue close` nor `issue comment`
- **Test:** `tests/test_issue_cleaner.py::test_dry_run_reports_the_close_and_mutates_nothing`
