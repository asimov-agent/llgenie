# stale-branch-silent-suppresses

## MODIFIED Requirements

### Requirement: the branch-list read must not suppress the response body (issue #1968)

`_paged_json` MUST read the repo's branch list through `gh api --paginate <endpoint>` WITHOUT
`--silent`, so a populated JSON array is returned. A persistent read failure (rc != 0, or an
unparseable body) MUST still red the daily run via `BranchListReadError` (#1514); a genuinely empty
`[]` list MUST still exit 0; a single transient fault (rc != 0 or empty stdout) MUST still be retried
once (#1602).

[comment]: # (AC / how to verify: tests/test_stale_branch_cleanup.py 11 pass; the new
test_branch_list_read_does_not_suppress_body_with_silent reds on the pre-fix script and passes with
the fix; report-only against the real API lists 55 would-delete / 12 kept at main 6940f9e7.)

#### Scenario: the branch list is read successfully

- **Given** a healthy GitHub API reachable through `gh`
- **When** `stale_branch_cleanup` runs in report-only mode
- **Then** it prints the would-delete set with per-branch evidence and exits 0

#### Scenario: a branch with an open PR is never deleted

- **Given** a non-`main`, age-eligible branch whose head ref is the head of an OPEN pull request
- **When** `stale_branch_cleanup` runs (report-only or `--apply`)
- **Then** the branch is REPORTED (`live vehicle (OPEN) — kept`) and never added to the delete set;
  the safety predicate (no open PR AND delivered) is what gates deletion, never age alone

#### Scenario: a persistent read failure reds, an empty list does not

- **Given** a branch-list read that fails on both attempts (rc != 0 or unparseable body)
- **When** `stale_branch_cleanup` runs
- **Then** it exits non-zero naming `branch-list read failed` (#1514, never a clean board)

- **Given** a repo whose branch list is a valid empty array `[]`
- **When** the sweep runs
- **Then** it exits 0 with "0 would be deleted"
