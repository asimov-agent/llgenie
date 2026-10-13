# agents-debt-analysis-issue-only

## ADDED Requirements

### Requirement: Every change is analysed into issues, never into the change

Every change MUST be analysed for real gaps and technical debt, and each
demonstrable finding MUST be filed as its own detailed issue — not implemented
inside the current change and not left as prose. `AGENTS.md` MUST state this rule
durably.

WHEN an agent works on any change,
THEN it analyses the change for real gaps and technical debt and files each
demonstrable finding as a separate, linked, detailed issue, and does not
implement that finding in the same change.

#### Scenario: the rule is in the rulebook and enforced

- **Given** the agent rulebook `AGENTS.md`
- **When** the analysis rule section is read
- **Then** it mandates analysis into issues ("ships issues, not code"), requires the findings to be separate linked issues, and forbids implementing them in the same change
- **And** `make test-unit` runs a test that fails if the rule text is removed
- **Test:** `tests/test_agents_debt_analysis.py::test_agents_md_requires_analysis_into_issues`
