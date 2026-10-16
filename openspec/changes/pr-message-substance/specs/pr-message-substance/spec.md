# pr-message-substance

## ADDED Requirements

### Requirement: A producer's commit message carries a body, not just a subject

Every `git commit` a producer the repository owns runs (a `.github/workflows/*.yml` step, the
`Makefile`, or `scripts/**`) SHALL pass a message that is a typed Conventional Commit subject
(`type(scope): summary`), is not a placeholder (`-`, `wip`, `update`, `fix`, `msg`, `tbd`, `todo`,
`n/a`, `x`, `.`), and carries a body — a second `-m`/`--message`, or a message containing a
newline. A bare subject SHALL be a violation.

#### Scenario: a bodiless commit is loud

- **GIVEN** a producer that runs `git commit -m "chore(engine): bump x to v1"`
- **WHEN** `make check-pr-hygiene` runs
- **THEN** it SHALL exit non-zero and report that the commit has no body
- **Test:** `tests/test_pr_hygiene.py::test_a_bodiless_commit_is_a_violation`

#### Scenario: a placeholder subject is loud

- **GIVEN** a producer that runs `git commit -m "update" -m "body"`
- **WHEN** the guard runs
- **THEN** it SHALL report the placeholder subject
- **Test:** `tests/test_pr_hygiene.py::test_a_placeholder_subject_is_a_violation`

#### Scenario: a subject, not a typed Conventional Commit

- **GIVEN** a producer that runs `git commit -m "bumped things" -m "body"`
- **WHEN** the guard runs
- **THEN** it SHALL report that the subject is not a typed Conventional Commit
- **Test:** `tests/test_pr_hygiene.py::test_a_subject_that_is_not_conventional_is_a_violation`

#### Scenario: a real message completes the fix

- **GIVEN** a producer that runs `git commit -m "chore(engine): bump x" -m "Issue: #1 ..."`
- **WHEN** the guard runs
- **THEN** it SHALL accept the commit
- **Test:** `tests/test_pr_hygiene.py::test_a_subject_and_body_is_accepted`

### Requirement: A producer's PR body is present and never a placeholder

Every `gh pr create` a producer runs SHALL pass `--body`, `--body-file` or `-b` with a value that is
not empty and not a placeholder. A missing body flag, `--body ""`, `--body "-"` and `--body "wip"`
SHALL each be a violation.

#### Scenario: a PR opened with no body

- **GIVEN** a producer that runs `gh pr create --title "x"`
- **WHEN** the guard runs
- **THEN** it SHALL exit non-zero and report the missing PR body
- **Test:** `tests/test_pr_hygiene.py::test_a_pr_with_no_body_is_a_violation`

#### Scenario: an empty or placeholder body

- **GIVEN** a producer that runs `gh pr create --title "x" --body ""`
- **WHEN** the guard runs
- **THEN** it SHALL report the placeholder body
- **Test:** `tests/test_pr_hygiene.py::test_an_empty_pr_body_is_a_violation`

#### Scenario: a body from a variable or a file is accepted

- **GIVEN** a producer that runs `gh pr create --body "$body"` or `--body-file p.md`
- **WHEN** the guard runs
- **THEN** it SHALL accept the PR
- **Test:** `tests/test_pr_hygiene.py::test_a_body_variable_or_file_is_accepted`

### Requirement: The mandate is pinned in AGENTS.md

`AGENTS.md` SHALL carry the mandate section that states the three parts a commit/PR message carries
(the issue, the fix, the benefit) plus the technical extension. Removing it SHALL be a violation, so
the rule cannot be deleted silently.

#### Scenario: the mandate section is removed

- **GIVEN** an `AGENTS.md` whose mandate heading is gone
- **WHEN** the guard runs
- **THEN** it SHALL report the missing mandate
- **Test:** `tests/test_pr_hygiene.py::test_a_missing_agents_mandate_is_a_violation`

### Requirement: The guard gates CI and this repository passes it

`make check-pr-hygiene` SHALL run inside the `ci-unit` job and SHALL exit non-zero on any violation.
Every producer in this repository SHALL pass it.

#### Scenario: the exit code is what CI gates on

- **WHEN** the guard finds a violation in a fixture tree
- **THEN** `main(["check"])` SHALL return non-zero, and 0 on this repository's tree
- **Test:** `tests/test_pr_hygiene.py::test_check_exits_non_zero_on_a_violation_and_zero_on_this_repo`

#### Scenario: this repository's producers all state the issue, the fix and the benefit

- **WHEN** the guard runs over this repository
- **THEN** it SHALL report no violation
- **Test:** `tests/test_pr_hygiene.py::test_this_repository_passes_its_own_guard`
