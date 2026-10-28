# agent-profiles

## ADDED Requirements

### Requirement: the host agents' behaviour has a home in this tree

Every host agent profile MUST have a directory under `agents/` holding its `SOUL.md` and its
`skills/<name>/SKILL.md`, and `agents/manifest.json` MUST list every profile that directory tree is
the source of truth for. A listed profile with no directory, or a directory the manifest does not
list, MUST be a failure: nothing syncs or gates it, so its behaviour stays unreviewable.

WHEN `agents/manifest.json` and the `agents/` directory disagree
THEN `make check-agent-profiles` fails, naming the profile and which side is missing.

#### Scenario: the committed tree lists and carries both host profiles

- **Given** the repository's `agents/` tree and its `manifest.json`
- **When** `make check-agent-profiles` reads them
- **Then** it exits 0, `llgenie-planner` and `llgenie-issse-implementer` are both listed, and each
  listed profile has a directory with a `SOUL.md`
- **Test:** `tests/test_agent_profiles.py::test_committed_tree_passes_the_gate`,
  `tests/test_agent_profiles.py::test_manifest_lists_both_host_profiles`

#### Scenario: a listed profile with no directory is a failure

- **Given** a manifest listing a profile whose directory does not exist
- **When** the gate reads the tree
- **Then** it reports `profile-directory`
- **Test:** `tests/test_agent_profiles.py::test_missing_profile_directory_is_rejected`

#### Scenario: a profile directory the manifest does not list is a failure

- **Given** an `agents/<profile>/` directory the manifest omits
- **When** the gate reads the tree
- **Then** it reports `profile-unlisted`
- **Test:** `tests/test_agent_profiles.py::test_profile_directory_the_manifest_does_not_list_is_rejected`

#### Scenario: no agents tree at all is a failure, not an empty pass

- **Given** a tree with no `agents/` directory
- **When** the gate runs
- **Then** it reports `agents-dir` and exits non-zero
- **Test:** `tests/test_agent_profiles.py::test_missing_agents_tree_is_rejected`

### Requirement: a profile's SOUL states the standing rules its manifest entry declares

A profile's `SOUL.md` MUST exist and MUST keep stating the standing rules `agents/manifest.json`
declares for it — `never-implement` and `never-merge` for the orchestrator. A manifest that declares
`never-merge` for no profile at all MUST itself be a failure, so the rule cannot be emptied out of
the manifest. A rule name the gate does not know MUST be a failure, never a silent pass.

WHEN a `SOUL.md` loses a declared standing rule, or the manifest stops declaring `never-merge`
THEN `make check-agent-profiles` fails, naming the profile and the rule.

#### Scenario: the orchestrator keeps both standing rules

- **Given** `agents/llgenie-planner/SOUL.md`
- **When** the gate matches each declared rule
- **Then** the text states both `never-implement` and `never-merge`
- **Test:** `tests/test_agent_profiles.py::test_committed_planner_soul_states_both_standing_rules`

#### Scenario: a planner SOUL that dropped the never-merge rule is a failure

- **Given** a planner `SOUL.md` carrying no never-merge rule
- **When** the gate reads it
- **Then** it reports `standing-rule`
- **Test:** `tests/test_agent_profiles.py::test_soul_that_dropped_never_merge_is_rejected`

#### Scenario: a manifest declaring never-merge for nobody is a failure

- **Given** a manifest whose profiles all carry an empty `rules` list
- **When** the gate reads it
- **Then** it reports `manifest-rule`
- **Test:** `tests/test_agent_profiles.py::test_manifest_that_declares_never_merge_for_nobody_is_rejected`

#### Scenario: a misspelt rule name is a failure

- **Given** a manifest entry declaring a rule the gate does not know
- **When** the gate reads it
- **Then** it reports `manifest-rule-unknown`
- **Test:** `tests/test_agent_profiles.py::test_unknown_rule_key_in_the_manifest_is_rejected`

#### Scenario: a profile with no SOUL.md is a failure

- **Given** a listed profile directory carrying no `SOUL.md`
- **When** the gate reads the tree
- **Then** it reports `soul-missing`
- **Test:** `tests/test_agent_profiles.py::test_profile_without_soul_is_rejected`

### Requirement: every committed skill is loadable and carries no credential

A committed skill's frontmatter `name` MUST equal its directory name (Hermes resolves a skill by the
frontmatter name), it MUST carry `name:`/`description:`, and a `references/<file>.md` its body names
MUST exist in the tree. No committed file of `agents/` may carry a secret-shaped value: these files
are read by an agent that holds write credentials.

WHEN a skill cannot be resolved, points at a missing recipe, or a token-shaped value is committed
THEN `make check-agent-profiles` fails, naming the file.

#### Scenario: a frontmatter name that disagrees with its directory is a failure

- **Given** a skill filed under a directory its frontmatter name does not match
- **When** the gate reads it
- **Then** it reports `skill-name`
- **Test:** `tests/test_agent_profiles.py::test_skill_name_that_differs_from_its_directory_is_rejected`

#### Scenario: a skill with no frontmatter block is a failure

- **Given** a `SKILL.md` that opens with prose instead of `---`
- **When** the gate reads it
- **Then** it reports `skill-frontmatter`
- **Test:** `tests/test_agent_profiles.py::test_skill_without_frontmatter_is_rejected`

#### Scenario: a reference file the tree does not carry is a failure

- **Given** a skill body naming `references/missing.md` that is not committed
- **When** the gate reads it
- **Then** it reports `skill-reference-missing`
- **Test:** `tests/test_agent_profiles.py::test_skill_reference_that_is_not_in_the_tree_is_rejected`

#### Scenario: a secret-shaped value in a skill is a failure

- **Given** a skill whose body carries a token-shaped value
- **When** the gate reads it
- **Then** it reports `secret`
- **Test:** `tests/test_agent_profiles.py::test_secret_shaped_value_in_a_skill_is_rejected`

### Requirement: a profile's data is never committed

`state.db`, `sessions/`, `memories/`, `logs/` and `.env` are a profile's data, not its behaviour, and
MUST NOT appear in `agents/`.

WHEN profile data is committed under `agents/<profile>/`
THEN `make check-agent-profiles` fails, naming the path.

#### Scenario: a committed state.db is a failure

- **Given** a `state.db` beside a profile's `SOUL.md`
- **When** the gate reads the tree
- **Then** it reports `forbidden-path`
- **Test:** `tests/test_agent_profiles.py::test_profile_data_in_the_tree_is_rejected`

### Requirement: the tree can be pushed into a profile, and read back

`make sync-agent-profile PROFILE=<p>` MUST copy every file `agents/<p>/` carries into that profile's
Hermes home (`--dest`, else `$HERMES_PROFILE_HOME`, else `~/.hermes/profiles/<p>/`) and MUST verify
the copy by reading every file back. `CHECK=1` MUST compare instead of writing and MUST exit non-zero
naming the first differing path. A profile the manifest does not list MUST exit 2, never pass
silently. The sync MUST NOT delete, and MUST NOT write anything outside the files the tree carries.

WHEN the sync runs
THEN the profile holds the tree byte for byte, or the run fails and names what differs.

#### Scenario: the tree is copied into a profile home and verified

- **Given** a temporary `HERMES_PROFILE_HOME`
- **When** `make sync-agent-profile PROFILE=llgenie-planner` runs
- **Then** it exits 0 and every file the tree carries is byte-identical in that home
- **Test:** `tests/test_agent_profiles.py::test_sync_copies_the_tree_into_a_temporary_profile_home`

#### Scenario: CHECK=1 names a tampered file

- **Given** a profile home the sync has just written, with one file edited afterwards
- **When** the sync runs with `CHECK=1`
- **Then** it exits 1 and names that path
- **Test:** `tests/test_agent_profiles.py::test_sync_check_passes_after_the_copy_and_names_a_tampered_file`

#### Scenario: the destination comes from HERMES_PROFILE_HOME

- **Given** `$HERMES_PROFILE_HOME` set and no `--dest`
- **When** the sync runs
- **Then** it writes to, and checks, that path
- **Test:** `tests/test_agent_profiles.py::test_sync_check_honours_HERMES_PROFILE_HOME`

#### Scenario: an unknown profile exits 2

- **Given** a profile name `agents/manifest.json` does not list
- **When** the sync runs
- **Then** it exits 2 and names the profiles it knows
- **Test:** `tests/test_agent_profiles.py::test_sync_of_an_unknown_profile_exits_2`

### Requirement: the two trees are documented apart

`.hermes/skills/README.md` MUST state the split — CI-leg skills under `.hermes/skills/`, host-agent
behaviour under `agents/` — and both new targets MUST carry a `## help` line, be named in
`docs/BOTS.md`, be declared in `.PHONY`, and leave `make check-docs`, `make check-wiring` and
`make check-agent-skills` green.

WHEN a new skill or profile is added without the split being stated
THEN `make check-docs` / `make check-wiring` fail, and the reviewer has no way to tell which tree an
agent's rule belongs in.

#### Scenario: the documentation surface stays green

- **Given** the change's `Makefile`, `.hermes/skills/README.md` and `docs/BOTS.md`
- **When** `make check-docs`, `make check-wiring` and `make check-agent-skills` run
- **Then** each exits 0
- **Test:** CI job `ci-unit` -> `make check-docs`, `make check-wiring`, `make check-agent-skills`
