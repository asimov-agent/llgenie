## ADDED Requirements

### Requirement: no agent skill exceeds the skill-writer character cap

Every `agents/*/skills/*/SKILL.md` SHALL be at most 100,000 characters, measured in characters.
`make check-agent-skills` SHALL report a `skill-over-char-limit` finding naming the file, the
character count, the overflow, and the remedy, and SHALL exit non-zero.

#### Scenario: a skill one character over the cap

- **GIVEN** an agent skill of 100,001 characters
- **WHEN** `make check-agent-skills` runs
- **THEN** it fails with `skill-over-char-limit` for that file, naming the overflow and the remedy
- **Test:** `tests/test_agent_skills.py::test_a_skill_over_the_char_limit_is_a_finding`

#### Scenario: a skill exactly at the cap

- **GIVEN** an agent skill of exactly 100,000 characters
- **WHEN** `make check-agent-skills` runs
- **THEN** no `skill-over-char-limit` finding is raised for it
- **Test:** `tests/test_agent_skills.py::test_a_skill_exactly_at_the_limit_passes`

#### Scenario: a multibyte skill at the cap in characters

- **GIVEN** an agent skill of 100,000 characters whose UTF-8 encoding exceeds 100,000 bytes
- **WHEN** `make check-agent-skills` runs
- **THEN** it passes, because the tool counts characters
- **Test:** `tests/test_agent_skills.py::test_the_limit_is_measured_in_characters_not_bytes`

### Requirement: the finding states the remedy

A finding that reports only a size teaches a lane to delete. The finding SHALL name what to do with
the overflow.

#### Scenario: the remedy is in the message

- **WHEN** a `skill-over-char-limit` finding is produced
- **THEN** its detail names `references/` and the one-line pointer
- **Test:** `tests/test_agent_skills.py::test_the_finding_carries_the_remedy_not_only_the_number`
