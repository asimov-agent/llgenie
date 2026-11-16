## ADDED Requirements

### Requirement: Duplicate-rule leak check is scoped to rule holders, not report text
The duplicate-canonical-rule test SHALL assert deduped-lane absence against the report's
**rule-holder lines** (entries matching `  <name>: <title> stated more than once`), never against
a substring of the whole report, so a host whose tmp/agents-root path happens to contain a
deduped lane name cannot manufacture a false red (issue #2330).

#### Scenario: Lane-named tmp base stays green
- **WHEN** the module runs with a pytest tmp base whose path embeds `llgenie-issse-implementer`
- **THEN** the test passes (the header path is not read as a rule holder)

#### Scenario: Clean tmp base stays green
- **WHEN** the module runs with `TMPDIR` under a path containing no lane name
- **THEN** the test passes

#### Scenario: Genuine re-flag of a deduped lane name still trips the check
- **WHEN** a synthetic profile named exactly `llgenie-tester` states a canonical rule twice
- **THEN** the report NAMES it as a rule holder and the scoped assertion catches it

#### Scenario: Substitution-collision proof intact
- **WHEN** the synthetic `lane` tree states one canonical title twice in its bolded form
- **THEN** the report names `lane:` while `findings()` stays empty (informational debt, never a gate red)
