# skill-size-cap-gate

## ADDED Requirements

### Requirement: An over-limit SKILL.md is a gate failure that names its remedy

The agent-profile gate SHALL fail when any `agents/<profile>/skills/<skill>/SKILL.md` body is longer than
the skill writer's 100,000-character cap, and its finding SHALL name the file, the overflow in characters,
and the remedy — moving sections into `references/` — rather than only the limit.

#### Scenario: a skill over the cap fails the gate with the remedy named

Given a tree whose `agents/<profile>/skills/<skill>/SKILL.md` is longer than 100,000 characters
When   `make check-agent-profiles` reads that tree
Then   it fails with a `skill-size` finding whose `where` names the SKILL.md
And    whose detail states the characters over the cap and that sections must move into `references/`

- **Test:** `tests/test_agent_profiles.py::test_a_skill_past_the_writer_cap_is_a_finding_that_names_the_remedy`

#### Scenario: slimming the same skill under the cap greens the gate

Given the same tree after that SKILL.md is rewritten under 100,000 characters
When   the gate reads it again
Then   no `skill-size` finding is reported

- **Test:** `tests/test_agent_profiles.py::test_a_skill_past_the_writer_cap_is_a_finding_that_names_the_remedy`

### Requirement: An exemption is a dated decision with a tracking issue, and expires

The gate SHALL accept an over-limit skill only through `tests/fixtures/skill-size-exceptions.json`, SHALL
still print each exempted file in its report, SHALL fail on an entry that carries no `reason`, `issue` or
`date`, and SHALL report a `skill-size-exemption-stale` finding once an exempted file is back under the cap
or is gone.

#### Scenario: an exempted over-limit skill is reported, not failed

Given an over-limit SKILL.md and a record entry naming a reason, an issue and a date for it
When   the gate reads that tree
Then   no `skill-size` finding is reported for that file
And    `make agent-profiles-report` names the file and the issue that removes the exemption

- **Test:** `tests/test_agent_profiles.py::test_an_over_limit_skill_with_a_dated_exemption_is_reported_not_failed`

#### Scenario: an expired exemption is a finding

Given a record entry for a skill whose body is already under the cap
When   the gate reads that tree
Then   it reports a `skill-size-exemption-stale` finding telling the reader to delete the entry

- **Test:** `tests/test_agent_profiles.py::test_an_exemption_whose_file_is_back_under_the_cap_is_stale`

#### Scenario: an exemption with no issue is a finding

Given a record entry that carries a reason but no issue and no date
When   the gate reads that tree
Then   it reports a `skill-size-exemptions` finding naming the missing fields

- **Test:** `tests/test_agent_profiles.py::test_an_exemption_with_no_issue_is_a_finding`

### Requirement: The planner orchestration body fits and loses nothing

`agents/llgenie-planner/skills/llgenie-bot-orchestration/SKILL.md` SHALL be under the cap in the tree, its
`## When to Use` text SHALL be preserved verbatim in `references/when-to-use-and-pass-shape.md`, and the
distinct lines of the pre-change body SHALL all appear in the slim body or the new reference.

#### Scenario: the section move preserves every distinct line

Given the pre-change SKILL.md at `origin/main` `c3f3b2ac`
When   its distinct lines are compared against the slim SKILL.md plus `references/when-to-use-and-pass-shape.md`
Then   the set difference is empty and the slim body is under 100,000 characters

- **Test:** measured in the change record `agent-wiki/2026-11-08-orchestration-skill-size-2084.md`;
  re-runnable with `git show origin/main:agents/llgenie-planner/skills/llgenie-bot-orchestration/SKILL.md`
  against the committed body and the new reference (the committed tree itself is gated by
  `make check-agent-profiles` in `make ci-unit`).
