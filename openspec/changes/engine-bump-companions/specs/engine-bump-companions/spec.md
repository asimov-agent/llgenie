# engine-bump-companions

## ADDED Requirements

### Requirement: a bump writes its companion note + index-row pair
When `bump(emit_companions=True)` pins an engine to a new upstream commit,
THEN it MUST write a dated `agent-wiki/<date>-engine-bump-<id>.md` note that
references the engine-bump issue (`#107`) and the pin delta
(`<old8> -> <new8>`), write the matching one-row `docs/changes.d/
<date>-engine-bump-<id>.md` fragment pointing at the note of its own name, and
rebuild `CHANGES.md` from the fragments — so the SAME commit that moves the pin
carries the note pair `make check-docs`' change→note rule (issue #1123) owes a
bump PR.

#### Scenario: the bump commits its note and row pair
- **Given** a skill whose pin moved, driven as the lane on a scratch tree
- **When** `bump("testengine", emit_companions=True)` runs
- **Then** exactly one `agent-wiki/2026-11-16-engine-bump-testengine.md` note and
  one `docs/changes.d/2026-11-16-engine-bump-testengine.md` fragment exist
- **And** the note mentions `#107` and `aaaaaaaa -> <new8>`
- **And** the fragment parses as one well-formed row whose `note` equals
  `2026-11-16-engine-bump-testengine.md`
- **And** `CHANGES.md` links the note and `changes_index.check` is clean
- **And** `check_docs.change_note_problems` is empty for a branch that changed a
  behavioural surface and added an `agent-wiki/` note
- **Test:** `tests/test_engine_bump.py::test_bump_writes_the_companion_note_and_row`

### Requirement: a library bump never writes the repo's companions
When `bump()` is called as a library flow with `emit_companions=False` (a unit
test driving a scratch tree), THEN it MUST NOT write `agent-wiki/`,
`docs/changes.d/` or `CHANGES.md` for the caller — the lane's repo writes are gated
behind the explicit switch, so a non-lane caller can never pollute the real repo.

#### Scenario: the flag is off for a library caller
- **Given** a skill whose pin moved
- **When** `bump("testengine")` runs with the default `emit_companions=False`
- **Then** no `agent-wiki/` or `docs/changes.d/` file is written, and `CHANGES.md`
  is untouched
- **And** the pre-existing `test_bump_applies_one_fixture_before_it_commits` /
  `test_bump_reports_packages_the_new_tag_removed` end-to-end fixtures still pass
  without a companion write
- **Test:** `tests/test_engine_bump.py::test_bump_rewrites_frozen_image_hash_asserts`
  (exercises the rewriter directly) and the two live-bump fixtures above

### Requirement: the frozen image-hash asserts the pin move makes stale are rewritten
When a bump moves the pin and `emit_companions=True`, THEN it MUST recompute each
variant's image hash from the regenerated params (after `_regen_guard`, so params
and Dockerfiles are final) and rewrite the frozen `es._image_hash(params,
"<variant>") == "<old8>"` equality asserts in `tests/` and `docs/` files that
reference `params/<id>.json` to the new hash — a `!= "<hash>"` moved assert stays
untouched.

#### Scenario: a version bump moves the frozen image hash
- **Given** a params file, its Dockerfile, entrypoint and runner on a scratch
  tree, and a test that asserts an OLD image hash (`== '7f000000'`) plus a
  `!= 'deadbeef'` moved assert
- **When** `_rewrite_image_hash_asserts("testengine")` runs
- **Then** the `==` literal is rewritten to the real derived hash and returned in
  the changed-files list
- **And** the `!= 'deadbeef'` moved assert is left untouched
- **And** a test file that does not reference `params/testengine.json` is not touched
- **Test:** `tests/test_engine_bump.py::test_bump_rewrites_frozen_image_hash_asserts`

### Requirement: the bump PR body names its OpenSpec change and stages the companions
When the bump workflow opens or updates the bump PR, THEN its body MUST carry an
`OPENSPEC: publish-changed-pin-images` line naming an ACTIVE change (issue #1807),
and the commit MUST stage `agent-wiki/`, `docs/changes.d/` and `CHANGES.md`
alongside the pin move — so the guard's openspec-change finding is absent and the
note pair reaches the commit.

#### Scenario: the template and staging carry the companions
- **Given** the `engine-bump.yml` workflow
- **When** the PR-opening step is read
- **Then** its body template contains `OPENSPEC: publish-changed-pin-images`, which
  `_active_change_names` confirms is an active change
- **And** the `git add` line stages `agent-wiki/`, `docs/changes.d/` and `CHANGES.md`
- **Test:** `tests/test_engine_bump.py::test_bump_pr_body_carries_openspec_line_and_stages_companions`
