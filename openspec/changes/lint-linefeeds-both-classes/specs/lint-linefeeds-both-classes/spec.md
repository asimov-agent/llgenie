## ADDED Requirements

### Requirement: report-both-lint-classes-before-returning

`scripts/lint_linefeeds.py check()` SHALL print the `trailing-newline` report when its class found a
defect, SHALL print the `markdown-heading` report when that class found a defect, and SHALL return 1
(once, at the end) if either class found a defect — never returning between the two reports — so a
file failing both classes names both in one result instead of masking the second until the first is
fixed.

#### Scenario: a file failing both classes names both

- **Given** a tracked file whose last line has no trailing newline and whose markdown heading is
  immediately preceded by non-blank content
- **When** `check` runs on it
- **Then** stdout carries both the `trailing-newline` and the `markdown-heading` report headers and
  the exit code is 1
- **Test:** `tests/test_lint_linefeeds.py::test_both_classes_are_reported_before_returning`

#### Scenario: a clean file still returns 0 via the aggregate OK

- **Given** a tracked file with a trailing newline and no markdown-heading defect
- **When** `check` runs on it
- **Then** it prints the aggregate OK line and returns 0
- **Test:** `tests/test_lint_linefeeds.py::test_clean_file_still_passes` (the existing clean-file
  acceptance)
