# engine-bump-pr-body

## ADDED Requirements

### Requirement: the engine-bump PR body is composed by one seam the workflow calls through make
The engine-bump lane MUST compose its pull-request body in `scripts/engine_bump_pr_body.py`, reached
through `make engine-bump-pr-body`, and the workflow's bump job MUST NOT compose any part of the body
inline. AGENTS.md forbids a workflow from running a raw script, and the inline composer is where the defect
lived: composing through `$(…)` throws away the newline a section depended on.

#### Scenario: the bump step calls the make target with the lane's own values
- **Given** the `bump` job's "Open / update the bump PR" step
- **When** the workflow text is parsed
- **Then** it calls `make engine-bump-pr-body` with `ENGINE/REF/OLD/NEW/RUN/OUT` and `COMMIT_OUT`
- **And** the body file it stamps and opens the PR with is the renderer's output
- **Test:** `tests/test_engine_bump_pr_body.py::test_the_body_renderer_is_wired_through_make`

#### Scenario: the inline composer may not come back
- **Given** the executable lines of the same step (its comment may name the old composer)
- **When** they are inspected
- **Then** no `body=$(printf …)` composition and no `$(cat params-review-section.md)` append remain, and the
  renderer is reached only through the make target
- **Test:** `tests/test_engine_bump_pr_body.py::test_the_inline_body_composer_is_gone`

### Requirement: every section of the composed body ends its line and the OpenSpec reference parses
The renderer MUST join sections with a blank line, MUST render the optional hard-fail warning, dependency
line and params documentation review as their own sections, and MUST emit the `OPENSPEC: <change>` line as
the last line of the body with nothing after the change name, so that
`scripts/check_pr_hygiene.py::OPENSPEC_REF` reads the change name back out of the body.

#### Scenario: a documentation review cannot glue itself onto the change name
- **Given** a bump whose params review section is non-empty
- **When** the body is rendered
- **Then** the review heading starts on its own line after a blank line
- **And** the only `OPENSPEC:` line is exactly `OPENSPEC: publish-changed-pin-images`
- **Test:** `tests/test_engine_bump_pr_body.py::test_the_openspec_reference_survives_the_documentation_review`

#### Scenario: the body is made of real newlines
- **Given** a bump body rendered with the lane's facts
- **When** the bytes are compared to the expected rendering
- **Then** it matches, with no literal `\n` anywhere and the `**bold**` markers rendered for real
- **Test:** `tests/test_engine_bump_pr_body.py::test_pr_body_has_real_newlines_not_literal_backslash_n`

#### Scenario: the optional sections stay optional
- **Given** a bump with a hard-fail param, a dependency line, or neither
- **When** the body is rendered
- **Then** the hard-fail warning and the `- **Dependencies:**` line appear as their own paragraphs, and
  neither appears when its input is empty
- **Test:** `tests/test_engine_bump_pr_body.py::test_hard_fail_appends_a_warning_paragraph`
- **Test:** `tests/test_engine_bump_pr_body.py::test_dependency_line_appends`

### Requirement: the bump PR body carries its own ticked, provable acceptance checklist
The composed body MUST carry `## Acceptance criteria` with one checkbox per provable outcome, ticked, each
carrying a proven clause in a form `scripts/check_pr_acceptance.py::_is_provable_tick` accepts (the lane's
own GitHub Actions run id, replayable through `gh run view`), so that `make check-pr-acceptance-form`
(mk/gates.mk:142, issue #1796) and the self-tick audit (issue #745) both pass on a bump body.

#### Scenario: the checklist the scope gate reads exists in the body
- **Given** a rendered bump body
- **When** `acceptance_writeback.acceptance_items` parses it
- **Then** it returns at least one item, every item is `- [x]`, and every item names a CI run or a
  command+rc+sha
- **Test:** `tests/test_engine_bump_pr_body.py::test_the_body_carries_the_acceptance_checklist_the_scope_gate_reads`

#### Scenario: the lane writes the body and the mirror to files
- **Given** `main()` called with the lane's arguments and a review file that does not exist
- **When** it runs
- **Then** it exits 0, writes the body to `--out` and the `## Acceptance:` mirror to `--commit-out`, and a
  missing optional review file is not a failure
- **Test:** `tests/test_engine_bump_pr_body.py::test_the_cli_writes_the_body_and_the_commit_mirror`

### Requirement: the bump commit's text mirrors the body's ticked items
The renderer MUST also emit the same ticked block under a `## Acceptance:` heading, and the lane MUST pass
it as a commit-message paragraph, so the joined commit text that `make check-pr-commit-checkboxes`
(mk/gates.mk:135, issue #2519) reads mirrors the pull-request body's ticks.

#### Scenario: the joined commit text mirrors the body
- **Given** the bump commit's messages plus the renderer's mirror
- **When** `check_pr_hygiene.commit_text_findings` compares them to the body
- **Then** it reports no finding
- **Test:** `tests/test_engine_bump_pr_body.py::test_the_commit_text_mirrors_the_body_ticks`

#### Scenario: a commit without the mirror is named
- **Given** the same body and commit messages without the mirror paragraph
- **When** the comparison runs
- **Then** it reports `commit-acceptance-unmirrored`
- **Test:** `tests/test_engine_bump_pr_body.py::test_a_commit_without_the_mirror_is_refused`

#### Scenario: the generated commit still claims no issue
- **Given** the bump lane's commit messages and title (a weekly rolling pin)
- **When** `check_pr_closing` reads claims out of them
- **Then** the bump lane claims no issue and the squash check reports nothing (issue #1588)
- **Test:** `tests/test_engine_bump_pr_body.py::test_generated_commit_message_does_not_trip_the_closing_gate`

### Requirement: `check-pr-openspec-change` names the shape of the reference it actually saw
When a pull-request body's OpenSpec reference fails, the finding MUST say which of the three shapes it saw —
an `OPENSPEC:` line that does not parse, a line naming a change that is not ACTIVE here, or no line at all —
so a producer with a line already in place is not sent to add one.

#### Scenario: a glued reference is reported as malformed
- **Given** a body carrying `OPENSPEC: publish-changed-pin-images## Documentation review`
- **When** `openspec_change_findings` runs
- **Then** the finding names the malformed line and states that the reference must end after the change name
- **Test:** `tests/test_pr_hygiene_openspec_change.py::test_openspec_change_finding_names_a_glued_reference`

#### Scenario: a name that is not an active change is named
- **Given** a body carrying a well-formed `OPENSPEC:` line for a change that is not ACTIVE
- **When** the gate runs
- **Then** the finding names the change and states that it is not ACTIVE on the branch or on main
- **Test:** `tests/test_pr_hygiene_openspec_change.py::test_openspec_change_finding_names_an_inactive_change`

#### Scenario: no reference at all still gets the original instruction
- **Given** a body with no `OPENSPEC:` line and no change file in the diff
- **When** the gate runs
- **Then** the finding keeps the `make openspec-new` instruction
- **Test:** `tests/test_pr_hygiene_openspec_change.py::test_openspec_change_finding_names_a_missing_reference`
