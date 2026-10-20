# engine-bump

## ADDED Requirements

### Requirement: a test that needs a kind synthesizes that kind's skill

The TensorFold suites MUST obtain the pip kind and the archive kind from **synthesized** skills, so
neither depends on what the repository's own `skills/engines/tensorfold/SKILL.md` currently
declares. A test that reads the kind off the repo skill MUST NOT exist.

#### Scenario: the pip kind is synthesized, not read off the repo skill

- **Given** a test that needs the pip install kind
- **When** it takes the skill from the `tf` fixture
- **Then** it SHALL run against a synthesized pip-shaped skill, whatever kind `main` declares
- **Test:** `tests/test_tensorfold_seamless.py::test_a_host_without_uv_only_blocks_the_pip_install`

#### Scenario: the no-uv test proves both kinds, from synthesized skills

- **Given** the synthesized pip skill and the synthesized archive skill
- **When** llgenie ensures TensorFold on a PATH without uv
- **Then** the archive kind installs and reaches its pinned release
- **And** the pip kind is refused with `missing prerequisite: uv`
- **Test:** `tests/test_tensorfold_seamless.py::test_a_host_without_uv_only_blocks_the_pip_install[pip]`
  and `tests/test_tensorfold_seamless.py::test_a_host_without_uv_only_blocks_the_pip_install[archive]`

### Requirement: the end-to-end pick tests assert the pick, not a hardcoded command

The two subprocess pick tests MUST assert that exactly one install ran and reached the pinned
release, in the step the skill declares. They MUST NOT assert a literal `uv tool install` line,
which fails once a bump moves the install to a release archive.

#### Scenario: the pick test asserts the install, whatever kind it is

- **Given** a Mac without TensorFold and a local TensorFold checkpoint
- **When** `llgenie --select 1 --engine tensorfold` (and the interactive pick) runs
- **Then** exactly one install ran, through the skill's declared step, leaving the pinned release
  installed
- **Test:** `tests/test_tensorfold_seamless.py::test_llgenie_pick_installs_tensorfold_then_execs_its_start_script`
  and `tests/test_tensorfold_seamless.py::test_interactive_llgenie_lists_pick_qwen38_27b_then_tensorfold_which_installs_and_serves`

### Requirement: the live release test feeds the derivation a pip-shaped skill

`release_archive_install`'s contract is a skill that pip-installs from git. The live release test
MUST pass that skill, and MUST additionally assert that an already-archive-shaped skill derives
nothing — never read the kind off the repo skill.

#### Scenario: the derivation is fed a pip-shaped skill, and refuses an archive one

- **Given** the published TensorFold v1.0.5 release and a pip-shaped skill
- **When** the derivation classifies the release
- **Then** both backends' archives are derived
- **And** the repo's own skill, when it is already archive-shaped, derives nothing
- **Test:** `tests/test_engine_bump.py::test_tensorfold_v1_0_5_release_is_native_archives`
