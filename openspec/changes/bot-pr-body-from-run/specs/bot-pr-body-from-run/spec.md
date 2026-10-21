# bot-pr-body-from-run

## ADDED Requirements

### Requirement: The PR body is the run's own material, validated before the PR opens

`open_pr()` SHALL build a bot PR's body from a file the implement step wrote (`pr-body.md`), SHALL require
non-empty `Issue:` / `Fix:` / `Benefit:` / `Technical:` parts and a reference to `#<issue>`, SHALL append
the pushed commit's file list and the `closes #<issue>` marker, and SHALL refuse — before any `gh` call —
when the file is missing or a part is absent, empty, or the body names no issue.

WHEN the PR is opened for an issue
THEN the body SHALL carry the four AGENTS.md parts in order, the files the commit touched, and
`closes #<issue>`; and WHEN the body file is missing or thin, THEN the command SHALL exit non-zero
naming what is wrong and SHALL NOT create the PR.

#### Scenario: no body file, no PR

Given an implement step that wrote no `pr-body.md`
When  `make issue-bot-open-pr` runs
Then  it refuses, naming the file and the required parts, and `gh` is never invoked — a description that
      says nothing cannot be published.

- **Test:** `tests/test_bot_pr_body.py::test_a_missing_pr_body_file_refuses_the_pr`

#### Scenario: a missing part is named

Given a body with `Issue:`, `Fix:` and `Technical:` but no `Benefit:`
When  the body is rendered
Then  the refusal names `Benefit:`, so the author learns which part is missing rather than getting a
      generic refusal.

- **Test:** `tests/test_bot_pr_body.py::test_a_body_missing_a_part_is_refused`

#### Scenario: a label with nothing after it is not a part

Given a body whose `Fix:` line carries no content
When  the body is rendered
Then  the refusal names `Fix:` — an empty label is the placeholder defect in another spelling.

- **Test:** `tests/test_bot_pr_body.py::test_a_part_with_no_content_is_refused`

#### Scenario: the body names the issue it implements

Given a complete four-part body that never mentions `#<issue>`
When  it is rendered for that issue
Then  it is refused, because `closes #<n>` alone is not a statement of what was implemented.

- **Test:** `tests/test_bot_pr_body.py::test_a_body_that_does_not_name_the_issue_is_refused`

#### Scenario: a real body carries the four parts, the file list and the closing marker

Given a four-part body and the commit's `--stat` output
When  the body is rendered
Then  it carries `Issue:`, `Fix:`, `Benefit:`, `Technical:` in that order, then `Files changed:` with the
      commit's own list, and ends with `closes #<issue>`.

- **Test:** `tests/test_bot_pr_body.py::test_a_real_body_carries_the_four_parts_the_stat_and_the_closes_marker`

### Requirement: The PR subject is derived from the issue and typed

`pr_title()` SHALL keep an issue title that already reads as a typed Conventional Commit, prefix `feat: `
otherwise, and append `(#<issue>)` — never a fixed string such as `issue-bot implementation`.

WHEN a PR subject is built from an issue title
THEN it SHALL be a typed Conventional Commit carrying the issue number.

#### Scenario: a typed issue title is kept

Given the issue title `ci(bots): the smoke proves a tool call` for #407
When  the subject is built
Then  it is `ci(bots): the smoke proves a tool call (#407)`.

- **Test:** `tests/test_bot_pr_body.py::test_the_title_is_the_issues_typed_subject_or_a_typed_prefix`

### Requirement: The producer carries no fixed title or placeholder, and the body is a run input

The `issue-bot-open-pr` recipe SHALL pass a body file and SHALL NOT carry `--wants` or a hardcoded
title; the implementer's prompt SHALL ask the agent for the four-part body; and `pr-body.md` SHALL be
ignored by git.

WHEN the producer, the prompt and the tree are inspected
THEN the recipe takes the body from a file with no fixed title, the prompt names `pr-body.md` and the
four parts, and `git check-ignore` reports `pr-body.md` as ignored.

#### Scenario: the fixed title and placeholder are gone from the recipe

Given the `issue-bot-open-pr` recipe
When  its argv is read
Then  it passes `--body-file`, and carries neither `--wants` nor `issue-bot implementation`.

- **Test:** `tests/test_bot_pr_body.py::test_the_producer_passes_a_body_file_and_no_fixed_title`

#### Scenario: the agent is asked for the body

Given the implementer's prompt
When  its rules are read
Then  it names `pr-body.md` and all four parts, so the file exists before the PR step runs.

- **Test:** `tests/test_bot_pr_body.py::test_the_implement_prompt_asks_for_the_body_before_it_finishes`

#### Scenario: the body file is ignored

Given the repository as committed
When  `git check-ignore` is asked about `pr-body.md`
Then  it is ignored, so `git add -A` cannot ship the description as the change.

- **Test:** `tests/test_bot_pr_body.py::test_the_pr_body_is_an_ignored_run_input`
