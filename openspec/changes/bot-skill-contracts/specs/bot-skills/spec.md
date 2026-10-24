# bot-skills

## ADDED Requirements

### Requirement: every bot leg's contract is a project skill loaded with `-s`

A `hermes -z` leg MUST preload its contract as a project skill (`.hermes/skills/<name>/SKILL.md`)
with `-s <bot>,bot-unattended`, and MUST NOT carry the rules inline. The skill MUST have a
frontmatter `name:` equal to its directory and MUST carry `## Inputs`, `## Output` and `## Rules`.

WHEN a bot leg is read
THEN its `-s` names existing, complete skills, and its inline prompt is a pointer plus that run's
parameters.

#### Scenario: the real tree's legs all load their skill

- **Given** the repository's `Makefile`, `scripts/fix_loop.sh` and `.hermes/skills/`
- **When** `make check-agent-skills` runs
- **Then** every `hermes -z` leg preloads `bot-unattended` and each named skill exists, is named for its directory and carries the three sections
- **And** the check exits 0
- **Test:** `tests/test_agent_skills.py::test_the_real_tree_has_one_complete_skill_per_leg_and_passes_the_gate`

#### Scenario: a leg that preloads no skill fails

- **Given** a leg whose whole contract is inline and which passes no `-s`
- **When** the gate checks it
- **Then** it exits non-zero, naming the leg and the missing preload
- **Test:** `tests/test_agent_skills.py::test_a_leg_with_no_skill_fails`

### Requirement: a skill is loadable by name and complete

A `-s <name>` MUST resolve to `.hermes/skills/<name>/SKILL.md`; that file's frontmatter `name:`
MUST equal `<name>`, and it MUST carry `## Inputs`, `## Output` and `## Rules`. A missing skill, a
name mismatch or a missing section MUST be an error that names the file.

WHEN a skill directory and its frontmatter are read
THEN a leg can load it by the name it preloads, and a contract cannot half-exist.

#### Scenario: a leg names a skill directory that does not exist

- **Given** a leg whose `-s` list includes a name with no `SKILL.md`
- **When** the gate checks it
- **Then** it exits non-zero and names the missing skill path
- **Test:** `tests/test_agent_skills.py::test_a_leg_naming_a_missing_skill_fails`

#### Scenario: a skill's frontmatter disagrees with its directory

- **Given** `.hermes/skills/issue-triage/SKILL.md` whose frontmatter says `name: triage`
- **When** the gate checks it
- **Then** it reports the declared and expected names
- **Test:** `tests/test_agent_skills.py::test_a_skill_whose_name_differs_from_its_directory_fails`

#### Scenario: a skill is missing a contract section

- **Given** a skill with no `## Output` section
- **When** the gate checks it
- **Then** it names the missing section
- **Test:** `tests/test_agent_skills.py::test_a_skill_missing_a_contract_section_fails`

### Requirement: the inline prompt is a pointer, and the shared contract exists once

An inline prompt MUST stay under the pointer budget (`MAX_PROMPT_CHARS`, 400) and MUST NOT repeat
the shared unattended wording. A prompt that grows back into a rulebook, or a returning second
rules file, MUST fail.

WHEN a recipe's prompt grows
THEN the gate reds and names the budget or the duplicated contract.

#### Scenario: a rulebook-sized prompt is refused

- **Given** a leg whose inline prompt is longer than the budget
- **When** the gate checks it
- **Then** it reports the measured length against the 400-char budget
- **Test:** `tests/test_agent_skills.py::test_an_inline_prompt_over_the_pointer_budget_fails`

#### Scenario: the unattended paragraph is pasted back into a recipe

- **Given** a leg whose inline prompt repeats `NEVER ask a question`
- **When** the gate checks it
- **Then** it points at `bot-unattended` as the one home
- **Test:** `tests/test_agent_skills.py::test_a_prompt_repeating_the_shared_contract_fails`

#### Scenario: a second rules file returns

- **Given** a tree carrying `scripts/fix_bot_rules.md` next to the skills
- **When** the gate checks it
- **Then** it reports the second rules file
- **Test:** `tests/test_agent_skills.py::test_a_returning_second_rules_file_fails`

### Requirement: the image trusts the checkout, and the gate cannot go quiet

The agent image MUST set `skills.trusted_project_dirs` to `/repo` and prove it landed, because
Hermes discovers project skills only under a trusted root. The gate MUST also fail on the rule's
removal and on a tree that has no `hermes -z` leg at all (a scan must not pass on nothing).

WHEN the image installs Hermes
THEN `/repo` is trusted, and the leg's `-s` can resolve.

#### Scenario: the image trusts /repo for project skills

- **Given** `scripts/install_hermes_ci.sh` and the agent Dockerfile
- **When** their trust configuration is read
- **Then** the install sets `skills.trusted_project_dirs` to `/repo` and reads it back, and the image runs that script
- **Test:** `tests/test_agent_skills.py::test_the_agent_image_trusts_the_checkout_for_project_skills`

#### Scenario: the rule is removed from the rulebook

- **Given** a checkout whose `AGENTS.md` and `docs/AGENT-SKILLS.md` no longer carry the rule
- **When** the gate checks it
- **Then** it reports the rule as gone
- **Test:** `tests/test_agent_skills.py::test_removing_the_rule_from_the_rulebook_fails`

#### Scenario: a tree with no leg at all cannot pass

- **Given** a Makefile with no `hermes -z` invocation
- **When** the gate checks it
- **Then** it says the scan found nothing and exits non-zero
- **Test:** `tests/test_agent_skills.py::test_a_tree_with_no_leg_at_all_cannot_pass`
