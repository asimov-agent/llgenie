# code-review-bot

## ADDED Requirements

### Requirement: The bot files issues and nothing else

A run SHALL create one issue per NEW finding. It SHALL NOT edit a file, create a branch, push, open a
PR, merge, or comment on any issue or PR. A finding already filed SHALL be recognised by the marker
`<!-- code-review:<key> -->` in an issue body and SHALL NOT be filed again, and the number of issues
filed in one run SHALL NOT exceed the cap.

#### Scenario: a second run on an unchanged tree is silent

- **GIVEN** a tree whose findings have all been filed
- **WHEN** the filer runs again
- **THEN** it SHALL create no issue and SHALL exit 0
- **Test:** `tests/test_code_review.py::test_an_already_filed_finding_is_not_filed_again`

#### Scenario: the cap bounds a bad run

- **GIVEN** six findings and a cap of three
- **WHEN** the filer runs
- **THEN** exactly three issues SHALL be created
- **Test:** `tests/test_code_review.py::test_the_cap_holds_and_filing_stops_cleanly`

#### Scenario: issues only

- **WHEN** the filer runs
- **THEN** every `gh` call it makes SHALL start with `issue list` or `issue create`
- **Test:** `tests/test_code_review.py::test_the_bot_never_writes_code`

### Requirement: Every filed issue carries the evidence it was derived from

An issue body SHALL state what was measured, in which file or workflow, so a reviewer can verify the
claim without re-deriving it. `--dry` SHALL print what would be filed and create nothing.

#### Scenario: the evidence travels with the claim

- **WHEN** the filer creates an issue for a finding
- **THEN** the body SHALL contain the finding's evidence, the check that produced it, its location,
  and the marker
- **Test:** `tests/test_code_review.py::test_filing_creates_one_issue_per_new_finding_carrying_the_marker_and_the_evidence`

#### Scenario: a dry run writes nothing

- **WHEN** the filer runs with `--dry`
- **THEN** no issue SHALL be created
- **Test:** `tests/test_code_review.py::test_dry_run_creates_nothing`

### Requirement: A check states only what the repository can prove

A check SHALL NOT report a finding that its own inputs do not support: a `workflow_call`-only file
SHALL NOT be judged on its run count, an hourly or step cron SHALL NOT be reported as a collision,
and a step whose whole job is gh/git orchestration SHALL NOT be reported as an inline script.

#### Scenario: a reusable pipeline is not judged on runs GitHub attributes to its caller

- **GIVEN** `pipeline.yml` (`workflow_call` only) with 0 runs, and `ci.yml` which calls it three times
- **WHEN** the never-ran check runs
- **THEN** it SHALL report nothing for `pipeline.yml`
- **Test:** `tests/test_code_review.py::test_a_reusable_only_workflow_is_not_judged_on_its_run_count`

#### Scenario: only fixed slots can collide

- **GIVEN** two workflows both scheduled `43 * * * *`
- **WHEN** the collision check runs
- **THEN** it SHALL report nothing
- **Test:** `tests/test_code_review.py::test_a_collision_needs_a_fixed_slot`

#### Scenario: the documented exemption is honoured

- **GIVEN** a step that only calls `gh api` in a loop
- **WHEN** the inline-script check runs
- **THEN** it SHALL report nothing
- **Test:** `tests/test_code_review.py::test_gh_orchestration_may_stay_shell`

### Requirement: A refused API read is loud, not fatal

When a check that needs the GitHub API is refused for lack of permission, the run SHALL report that
the check is skipped and SHALL continue with the checks that do not need it.

#### Scenario: a token without admin still produces the static findings

- **GIVEN** a `gh` that fails `secret list` with a permission error
- **WHEN** the bot scans
- **THEN** it SHALL warn that the check is skipped and SHALL still return the static findings
- **Test:** `tests/test_code_review.py::test_a_refused_api_read_degrades_loudly_instead_of_crashing`

### Requirement: The bot passes its own checks

The workflow this change adds SHALL NOT be a finding of any check in this change, and it SHALL be
covered by the never-ran check like any other self-triggered workflow.

#### Scenario: self-consistency

- **WHEN** the checks run over the repository
- **THEN** no finding SHALL name `code-review-bot.yml`
- **Test:** `tests/test_code_review.py::test_the_bots_own_workflow_passes_the_bots_own_checks`
