# fix-engine-bump-allow-skill — spec

## MODIFIED Requirements

### Requirement: regen guard
After a bump, the working tree MAY contain only the bumped engine's
`skills/engines/<id>/SKILL.md`, `containers/engines/params/<id>.json` and
`containers/engines/dockerfiles/<id>/*`. The pin edit of the skill is the bump,
not a stray file. A diff anywhere else (including another engine's skill or
params) MUST fail the job.

#### Scenario: the bumped skill is allowed
- **Given** a bump whose working tree holds `skills/engines/<id>/SKILL.md` and that engine's params
- **When** the regen guard reads the working tree
- **Then** it does not fail
- **Test:** `tests/test_engine_bump.py::test_regen_guard_allows_the_bumped_skill`

#### Scenario: bump of A cannot change B's params
- **Given** a bump of engine A whose working tree changes engine B's params
- **When** the regen guard reads the working tree
- **Then** the job fails naming B's file
- **Test:** `tests/test_engine_bump.py::test_regen_guard_isolates_engine`, `tests/test_engine_bump.py::test_regen_guard_rejects_another_engines_skill`
