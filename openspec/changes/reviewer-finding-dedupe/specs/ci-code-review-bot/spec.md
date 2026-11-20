## ADDED Requirements

### Requirement: The code-review bot skips findings an open PR already fixes

The code-review bot SHALL NOT file an issue for a finding whose named file is changed by an open
pull request in the same repository, and the filing run's output SHALL name the in-flight PR.
The existing marker dedupe SHALL keep working unchanged, and a finding whose in-flight PR closes
without the fix SHALL be filed by a later run.

#### Scenario: Open PR touching the finding's file

- **WHEN** `code_review.py file` scans a finding and an open PR lists that finding's file among its
  changed files
- **THEN** no issue is created for that finding, and the run's output contains
  `already in flight: PR #<n>` naming the PR

#### Scenario: No open PR touching the file

- **WHEN** the same finding is scanned and no open PR touches its file (and no marker matches)
- **THEN** the finding is filed as before

#### Scenario: The open-PR read is refused

- **WHEN** the API refuses the open-PR listing
- **THEN** the run prints a WARNING that the in-flight check is degraded and proceeds with filing
  under the marker dedupe alone, never a silent skip
