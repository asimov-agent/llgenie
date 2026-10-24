# bot-agent-skills

## ADDED Requirements

### Requirement: every agent leg loads its contract from a Hermes project skill

Each `hermes -z` leg in the `Makefile` and in `scripts/*.sh` MUST preload at least one skill with
`-s <name>` (or `--skills`), and every name MUST resolve to `.hermes/skills/<name>/SKILL.md` whose
frontmatter `name` equals that directory. A leg that preloads nothing, or names a skill the tree does
not carry, MUST be a finding — such a leg runs with no contract at all and reports success.

WHEN the gate reads every agent leg in the repository
THEN each leg names a skill that exists, and the repository has no finding.

#### Scenario: this repository's legs all resolve

- **Given** the legs in `Makefile` and `scripts/*.sh`
- **When** `scripts/check_agent_skills.py check` reads them
- **Then** every leg preloads an existing skill and the gate exits 0
- **Test:** `tests/test_agent_skills.py::test_this_tree_passes_the_gate`

#### Scenario: a leg with no preload is refused

- **Given** a fixture tree whose leg carries no `-s`
- **When** the gate reads it
- **Then** it reports `leg-no-skill` for that leg
- **Test:** `tests/test_agent_skills.py::test_a_leg_without_a_preload_is_refused`

#### Scenario: a leg naming a missing skill is refused

- **Given** a fixture tree whose leg preloads a skill with no directory
- **When** the gate reads it
- **Then** it reports `leg-unknown-skill` and names the missing skill
- **Test:** `tests/test_agent_skills.py::test_a_leg_naming_a_missing_skill_is_refused`

### Requirement: the inline prompt is a pointer, not a rulebook

A leg's inline prompt MUST stay within a 400-character budget: it names the preloaded skill, the
input file, the output file and the run's parameters, and it MUST NOT restate the rules or repeat the
unattended contract, which live in the skills.

WHEN the gate measures a leg's inline prompt
THEN a prompt over the budget, or one carrying the unattended contract, is a finding.

#### Scenario: a rulebook creeping back into the recipe is refused

- **Given** a fixture leg whose prompt is 900 characters of rules
- **When** the gate measures it
- **Then** it reports `leg-prompt-budget` naming the budget
- **Test:** `tests/test_agent_skills.py::test_a_prompt_over_the_pointer_budget_is_refused`

#### Scenario: the unattended contract is not inlined again

- **Given** a fixture leg whose prompt repeats the unattended rule it also preloads
- **When** the gate reads it
- **Then** it reports `leg-inline-unattended`
- **Test:** `tests/test_agent_skills.py::test_the_unattended_contract_is_not_inlined_again`

#### Scenario: no real leg inlines the contract

- **Given** every agent leg of this repository
- **When** each one's prompt is read
- **Then** each preloads `bot-unattended` and none carries the rule's text inline
- **Test:** `tests/test_agents_unattended.py::test_every_leg_preloads_the_unattended_contract_and_none_inlines_it`

### Requirement: a skill is a complete, resolvable contract

Every skill directory MUST carry a `SKILL.md` with frontmatter (`name` equal to the directory,
non-empty `description`) and the three sections `## Inputs`, `## Output` and `## Rules`. A skill no leg
preloads MUST be reported, because a contract nothing loads is dead weight.

WHEN the gate reads `.hermes/skills/**/SKILL.md`
THEN each is resolvable by its directory name and states what it is given, may write and must not do.

#### Scenario: a frontmatter name that disagrees with its directory is refused

- **Given** a skill under `demo/` whose frontmatter says `name: something-else`
- **When** the gate reads it
- **Then** it reports `skill-name`, because `-s demo` resolves by the frontmatter name
- **Test:** `tests/test_agent_skills.py::test_a_skill_whose_name_disagrees_with_its_directory_is_refused`

#### Scenario: a skill with no Rules section is refused

- **Given** a skill that omits `## Rules`
- **When** the gate reads it
- **Then** it reports `skill-section` naming the missing section
- **Test:** `tests/test_agent_skills.py::test_a_skill_missing_a_section_is_refused`

#### Scenario: a skill no leg preloads is reported

- **Given** a skill directory no leg names
- **When** the gate reads the tree
- **Then** it reports `skill-unused`
- **Test:** `tests/test_agent_skills.py::test_a_skill_nothing_preloads_is_reported`

### Requirement: one mechanism for a bot's rules

`scripts/fix_bot_rules.md` MUST NOT exist: the fix bot's contract is the `pr-fix` skill, preloaded by
`scripts/fix_loop.sh`, and the rebase bot's prompt points at `rebase-conflict` instead of restating the
rules.

WHEN the gate reads the tree and the two scripts
THEN no second rules file exists and neither script restates a contract it preloads.

#### Scenario: a returned rules file is refused

- **Given** a tree that carries `scripts/fix_bot_rules.md` again
- **When** the gate reads it
- **Then** it reports `rules-file` and names the skill that replaced it
- **Test:** `tests/test_agent_skills.py::test_the_retired_rules_file_is_refused`

#### Scenario: the fix loop preloads instead of concatenating

- **Given** `scripts/fix_loop.sh`
- **When** its agent command and prompt are read
- **Then** it preloads `pr-fix,bot-unattended` and no longer `cat`s a rules file into the prompt
- **Test:** `tests/test_agent_skills.py::test_the_fix_bot_preloads_its_contract_instead_of_inlining_it`

### Requirement: Hermes really loads each leg's skills

The agent image MUST register the checkout's skill directory in the Hermes home
(`skills.external_dirs` → `/repo/.hermes/skills`) at build time and read the value back, and the load
itself MUST be proven through Hermes's own preload path: each leg's `-s` list fed to
`agent.skill_commands.build_preloaded_skills_prompt` MUST resolve every name and carry each skill's
content into the prompt the model receives.

WHEN a leg's preload list is fed to Hermes's preload path against the image's registration
THEN every skill resolves, its content is in the prompt, and an unregistered home resolves nothing.

#### Scenario: every leg's skills resolve and their content loads

- **Given** a Hermes home registered by `scripts/hermes_skills_register.py`, as the image registers it
- **When** each leg's `-s` list goes through Hermes's preload path
- **Then** no name is reported missing and each skill's description is in the rendered prompt
- **Test:** `tests/test_agent_skills_live.py::test_every_leg_resolves_its_skills_through_hermes_own_preload`

#### Scenario: an unregistered home loads nothing

- **Given** a Hermes home with no registration
- **When** a leg's preload list goes through the same path
- **Then** every name is reported missing and the rendered prompt is empty
- **Test:** `tests/test_agent_skills_live.py::test_an_unregistered_home_loads_nothing`

#### Scenario: the registration is a YAML list every Hermes version reads

- **Given** an empty Hermes home
- **When** the registration script runs twice for the same directory
- **Then** `config.yaml` holds a YAML list with one entry, and `--check` passes
- **Test:** `tests/test_agent_skills.py::test_the_register_script_writes_a_yaml_list_any_hermes_reads`

#### Scenario: the image registers the directory and reads it back

- **Given** `scripts/install_hermes_ci.sh`
- **When** its skill-registration section is read
- **Then** it runs the register script for `/repo/.hermes/skills` and verifies with `--check`
- **Test:** `tests/test_agent_skills.py::test_the_agent_image_registers_the_skills_directory`

### Requirement: the gate runs in CI and the rule is stated where it can be deleted

`make check-agent-skills` MUST run in `ci-unit`, be declared in `.PHONY`, carry a `make help` line and
be documented in `README.md`; `AGENTS.md` MUST state that a bot's behaviour lives in its project
skill, so the seam cannot be removed silently.

WHEN `make ci-unit` runs
THEN the gate is one of its stages, and an `AGENTS.md` without the rule is a finding.

#### Scenario: the gate is wired into ci-unit and into make

- **Given** the `Makefile`
- **When** its target, help line, `.PHONY` entry and `ci-unit` stage are read
- **Then** all four exist and `make -n check-agent-skills` prints the real command
- **Test:** `tests/test_agent_skills.py::test_the_gate_is_wired_into_ci_unit_and_make`

#### Scenario: an AGENTS.md that drops the rule is refused

- **Given** an `AGENTS.md` with no such heading
- **When** the gate reads the tree
- **Then** it reports `agents-md`
- **Test:** `tests/test_agent_skills.py::test_agents_md_must_state_the_rule`
