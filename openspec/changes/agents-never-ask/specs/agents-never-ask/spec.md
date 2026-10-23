# agents-never-ask

## ADDED Requirements

### Requirement: An unattended agent leg never asks a question

Every prompt that runs inside the agent image with no user attached SHALL state that the run is unattended,
that a question is a failure, and what to do instead (take the verdict that needs no decision, or the safest
reversible choice, and record it). `scripts/fix_bot_rules.md` SHALL carry the same rule for the repair loop.

WHEN an agent leg runs detached
THEN its prompt forbids asking, and a genuinely open decision becomes a `refine` with `REASON` (or the safest
reversible choice named in the output).

#### Scenario: every prompt carries the rule

Given the Makefile's five `hermes -z` prompts and the fix-bot's rules file
When  they are read
Then  each prompt contains the UNATTENDED rule, and the rules file has a "You are unattended" section naming
`clarify` and the exit code.

- **Test:** `tests/test_agents_unattended.py::test_every_unattended_prompt_forbids_asking_a_question`
- **Test:** `tests/test_agents_unattended.py::test_the_fix_bot_rules_forbid_asking_too`

### Requirement: Exit 3 is reported as "asked for input"

When the implement leg exits 3 (Hermes detached on a question), the issue-bot's failure step SHALL report it as
the agent asking for input, before and instead of the generic "changed nothing" message.

WHEN the implement leg exits 3
THEN the run names the question and points at the prompt's UNATTENDED rule.

#### Scenario: the failure step names the question

Given `.github/workflows/issue-bot.yml`
When  the failure step's body is read
Then  the `rc == 3` branch appears before the generic message and prints "the agent asked for input".

- **Test:** `tests/test_agents_unattended.py::test_exit_three_is_named_as_asked_for_input_not_changed_nothing`
