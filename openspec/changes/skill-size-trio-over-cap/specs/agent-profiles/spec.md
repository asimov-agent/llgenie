# Spec Delta: agent-profiles

## MODIFIED Requirements

### Requirement: The skill-writer size gate applies to every tree SKILL.md with no exemption in play

The `skill-size` finding SHALL fire when a tree `SKILL.md` body exceeds `SKILL_MAX_CHARS = 100_000` characters and the file is not named by a dated entry in `tests/fixtures/skill-size-exceptions.json`; an entry whose file is back under the cap SHALL itself be a finding (`skill-size-exemption-stale`) and must be deleted. After this change the record carries NO entries, so the gate is a plain pass/fail on the cap.

#### Scenario: every tree skill is under the cap

- **WHEN** `make check-agent-profiles` runs on a tree whose three formerly over-limit bodies have been slimmed by moving self-contained sections verbatim into `references/` files linked from the body
- **THEN** no `skill-size` finding and no `skill-size-exemption-stale` finding is reported, and `make check-agent-profiles-ratchet` is green
- **AND** each slimmed file measures under 100,000 characters at the fixing head

#### Scenario: no content is lost by the move

- **WHEN** the pre-change distinct-line set of a slimmed `SKILL.md` is checked against the union of the slim body's lines and the new `references/` files' lines
- **THEN** the check prints `LOST: 0` — every line the old body carried is still carried by the skill (body or linked reference)

#### Scenario: the exemption record ends empty

- **WHEN** `tests/fixtures/skill-size-exceptions.json` is read after the fix
- **THEN** its `files` map carries no entry for any of the three slimmed files (the record may remain as an empty map with its note; a missing record is the ordinary state)
