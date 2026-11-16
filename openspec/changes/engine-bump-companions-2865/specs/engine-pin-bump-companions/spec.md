# engine-pin-bump-companions

## ADDED Requirements

### Requirement: every bump carries its note pair
A bump commit produced by the engine-bump lane MUST add an
`agent-wiki/<stem>.md` note and the matching `docs/changes.d/<stem>.md` row
for the same stem, and the lane MUST stage `agent-wiki/` when it commits the
bump. The row MUST follow the changes.d row shape (date, description, wiki
link, reference) so `make check-docs`'s change->note contract is satisfied.

#### Scenario: a bump's containers diff has a note
- **Given** a bump of engine `<id>` on date `<date>`
- **When** the lane writes the bump commit
- **Then** `agent-wiki/<date>-<id>-bump.md` exists and names the bump lane issue
- **And** `docs/changes.d/<date>-<id>-bump.md` holds its row linked to that note
- **Test:** `tests/test_engine_bump_companions.py::test_companion_notes_shape`

### Requirement: the bump body names the active OpenSpec change
The bump PR body MUST carry a standalone `OPENSPEC: <active-change>` line so
the OpenSpec gate sees an artifact for a diff that touches product code.

#### Scenario: the rendered body passes the guard's OpenSpec regex
- **Given** the lane's body-assembly step renders a bump body
- **When** the body is assembled with `printf`
- **Then** the body contains a line matching `^OPENSPEC: [A-Za-z0-9_-]+$`
- **Test:** `tests/test_engine_bump_pr_body.py::test_rendered_body_names_the_active_openspec_change`

### Requirement: historical change rows survive a rewrite
`_rewrite_pin_asserts` MUST NOT rewrite `docs/changes.d/` rows: a row records
the pin pair that bump moved at its date, and a later bump rewriting it turns
a documented record into an undocumented one.

#### Scenario: a prior bump row keeps its old pin
- **Given** a fixture tree with `docs/changes.d/x.md` naming the old pin and a test naming it
- **When** `_rewrite_pin_asserts` runs for the engine
- **Then** the test literal moved to the new pin
- **And** the `docs/changes.d/` row still names the old pin
- **Test:** `tests/test_engine_bump_companions.py::test_rewrite_skips_changes_d_rows`

### Requirement: the engine's own current pins move with the bump
The lane MUST rewrite current-pin literals (registry image tags, `base:`
values) in the bumped engine's own SKILL.md, so `make generate-engine-params`
regenerates the params from the new pin instead of back-filling the old tag.

#### Scenario: the params' base tag follows the new ref
- **Given** a fixture SKILL.md with `base: <registry>:<old-ref>` and a history sentence naming the old ref
- **When** the rewrite runs for the engine
- **Then** the `base:` line names the new ref
- **And** prose that merely recalls the old ref is left alone
- **Test:** `tests/test_engine_bump_companions.py::test_skill_current_pins_move`

### Requirement: frozen image-hash asserts move with regen
When regen changes a variant's params so its image hash moves, the lane MUST
rewrite the frozen hash literals in `tests/` lines that name `_image_hash(` or
the engine's image tag, for the bumped engine only, before the PR is opened.

#### Scenario: regen's new hash is what the test asserts
- **Given** a fixture test with `assert es._image_hash(params, "cuda") == "<old8>"` and a tag comment naming `<old8>`
- **When** the frozen-hash rewrite runs with the moved pair
- **Then** the assert and the tag comment name the new hash
- **And** a line that names neither `_image_hash(` nor the engine tag is untouched
- **Test:** `tests/test_engine_bump_companions.py::test_frozen_image_hashes_move`

### Requirement: publish order defers a retagged engine
The publish-order read MUST defer an engine whose pin moved (its image tag
retags) even when its params file is byte-identical to the base ref, matching
the rule the test cites (issue #823: engines retagged since base defer their
`make publish-engine`).

#### Scenario: an identical params file for a moved engine is deferred
- **Given** a branch where an engine's pin moved and its params file equals base
- **When** the deferred-engine set is computed
- **Then** the engine is in it
- **Test:** `tests/test_ci_publish_order.py::test_an_identical_params_file_defers_only_when_a_tag_retags`
