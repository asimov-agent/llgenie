# pr-acceptance-form

## ADDED Requirements

### Requirement: a bot PR's body carries its own tickable `## Acceptance criteria` `- [ ]` checklist

When a bot-intended PR's range is checked, the PR body SHALL carry a `## Acceptance criteria` section
with at least one `- [ ] ` markdown checkbox, one per provable outcome (issue #745). Each criterion
SHALL be a checkbox a reviewer can tick; a criterion that cannot be ticked is not one. Otherwise the
gate SHALL refuse the PR with a finding naming the form rule (issue #1796) and the remedy (add the
`## Acceptance criteria` section with one `- [ ]` item per provable outcome). A human-intended range is
skipped — the rule is stated for the fleet lanes.

WHEN a bot PR's body carries no tickable acceptance checklist
THEN the gate exits non-zero and names the missing section and its remedy.

#### Scenario: a bot body with no acceptance checklist is refused

Given a bot PR whose body has no `## Acceptance criteria` section (or an empty one)
When  the acceptance-form gate runs
Then  it returns a finding naming issue #1796 and the `## Acceptance criteria` `- [ ]` remedy.

- **Test:** `tests/test_pr_hygiene_acceptance_form.py::test_a_bot_pr_with_no_acceptance_checklist_is_a_finding`
- **Test:** `tests/test_pr_hygiene_acceptance_form.py::test_a_bot_pr_with_empty_acceptance_section_is_a_finding`

#### Scenario: a bot body with `- [ ]` items passes

Given a bot PR whose body carries a `## Acceptance criteria` section with tickable `- [ ]` items
When  the acceptance-form gate runs
Then  it returns no finding (the body carries its own boxes for the reviewer to tick).

- **Test:** `tests/test_pr_hygiene_acceptance_form.py::test_a_bot_pr_with_a_real_checklist_passes`

#### Scenario: a human-only range is skipped, never failed

Given a PR whose range carries no bot-authored commit, and a body with no acceptance checklist
When  the acceptance-form gate runs
Then  it returns no finding (a human leg is not held to the bot form rule).

- **Test:** `tests/test_pr_hygiene_acceptance_form.py::test_a_human_only_range_is_skipped`

#### Scenario: the gate reuses acceptance_writeback and runs before check-pr-acceptance

Given the two guard workflows
When  `make check-pr-acceptance-form` runs on a PR body
Then  it imports `acceptance_items` (never restated), both `ci.yml` and `scope.yml` run the step with
      the live-body read (issue #1589) BEFORE `check-pr-acceptance` so the form verdict is not masked,
      and the Makefile target / `.PHONY` / `docs/BOTS.md` row / change-note trio are all present.

- **Test:** `tests/test_pr_hygiene_acceptance_form.py::test_the_acceptance_form_gate_is_wired_and_reuses_writeback`
