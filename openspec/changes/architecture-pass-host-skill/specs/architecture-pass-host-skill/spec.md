# architecture-pass-host-skill

## ADDED Requirements

### Requirement: A host skill lives in the tree, admitted by name

A Hermes project skill that no CI leg preloads SHALL live at `.hermes/skills/<name>/SKILL.md` and SHALL
be admitted by NAME in `HOST_SKILLS` (`scripts/check_agent_skills.py`). Admission SHALL exempt it from
the unused-skill rule only: it SHALL still owe frontmatter whose `name` matches its directory and the
`## Inputs` / `## Output` / `## Rules` sections.

WHEN a skill directory exists that no leg preloads
THEN it is refused as `skill-unused` unless its name is in `HOST_SKILLS`.

#### Scenario: an unadmitted skill is still dead weight

Given a skill no leg preloads and no `HOST_SKILLS` entry
When  `make check-agent-skills` runs
Then  it fails with `skill-unused` naming that skill.

#### Scenario: an admitted host skill is reported, not refused

Given an admitted host skill carrying frontmatter and the three sections
When  `make check-agent-skills` runs
Then  the run is green and `make agent-skills-report` prints it with a `host-skill` marker.

### Requirement: A contract section is an exact heading

The gate SHALL match each required section as an exact markdown heading line, never as a substring of
the body, so a renamed or decorated heading does not satisfy the contract.

WHEN a skill's `## Rules` heading is renamed (e.g. `## Rules for reviewers`)
THEN the gate reports the section as missing (`skill-section`).

#### Scenario: a decorated heading is a missing section

Given a skill whose heading is `## Rules for reviewers`
When  `make check-agent-skills` runs
Then  it fails with `skill-section` naming `## Rules`.
