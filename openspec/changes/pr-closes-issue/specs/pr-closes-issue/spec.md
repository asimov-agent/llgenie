# pr-closes-issue

## ADDED Requirements

### Requirement: The closing rule cannot be deleted from AGENTS.md silently

`AGENTS.md` SHALL state the closing rule — a PR that implements an issue closes it (`closes #<n>`),
and a PR that implements only part of an issue does not — and `make check-pr-hygiene` SHALL fail when
the rule's text is absent. The check SHALL read the closing rule as its own required text, separate
from the message mandate, so a missing closing rule is reported as its own finding with its own key
(`agents-closing-rule`) rather than being folded into the message-mandate finding.

#### Scenario: the closing rule is removed from AGENTS.md

- **WHEN** `AGENTS.md` carries the message-mandate heading but no longer states the closing rule
- **THEN** the guard SHALL fail, reporting the closing rule as its own finding and not the message
  mandate
- **Test:** `tests/test_pr_hygiene.py::test_a_missing_closing_rule_is_a_violation`

#### Scenario: both required texts are present

- **WHEN** `AGENTS.md` carries the message mandate and the closing rule
- **THEN** the guard SHALL report no `AGENTS.md` finding at all
- **Test:** `tests/test_pr_hygiene.py::test_agents_mandate_passes_when_the_closing_rule_is_present`

#### Scenario: this repository carries the closing rule

- **WHEN** this repository's `AGENTS.md` is read
- **THEN** it SHALL contain the closing rule verbatim, so this repo's own PRs follow it
- **Test:** `tests/test_pr_hygiene.py::test_this_repository_carries_the_closing_rule`
