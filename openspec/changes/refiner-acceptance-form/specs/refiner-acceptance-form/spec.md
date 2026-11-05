# refiner-acceptance-form

## ADDED Requirements

### Requirement: the refiner flags a body without the acceptance form
The issue-refiner's `/ refine` surface MUST call `issue_body.missing()` on the source body. When
it finds a shape defect, the agent's input (`refine-in.md`) MUST carry an
`## Acceptance-criteria form (issue #1796 #3)` finding naming every defect, so the review agent
restates with tickable `- [ ]` criteria. A body for which `issue_body.missing()` returns nothing
MUST pass through byte-identical.

WHEN the refiner writes the agent's input for a hand-authored issue body,
THEN `issue_body.missing()` is called on that body.

#### Scenario: a hand-authored body lacks a tickable acceptance form
- **Given** a hand-authored issue body with a `## Acceptance criteria` heading but no `- [ ]` item
- **When** the refiner renders the agent's input
- **Then** the input contains `## Acceptance-criteria form (issue #1796 #3)`
- **And** it names the exact `issue_body.missing()` defect
- **Test:** `tests/test_issue_refiner_form.py::test_render_flags_a_hand_authored_body_without_a_tickable_form`

#### Scenario: a conforming body passes through unchanged
- **Given** a producer-rendered body (`issue_body.missing()==[]`)
- **When** the refiner renders the agent's input
- **Then** the output contains no form finding
- **Test:** `tests/test_issue_refiner_form.py::test_render_leaves_a_conforming_body_byte_identical`

### Requirement: the finding reuses the reader and never edits the source
The refiner MUST reuse `issue_body.missing()` verbatim (never restate it), MUST NOT edit a human's
issue body, and MUST NOT fabricate `- [ ]` criteria that are not in the source.

WHEN the acceptance form is missing,
THEN the finding lists `issue_body.missing()`'s own findings and adds no invented checkboxes.

#### Scenario: missing sections are named, not invented
- **Given** a body with only `## Problem`
- **When** `acceptance_form_flag` runs
- **Then** the finding names every missing section and adds no `- [ ]` line that was not in the source
- **Test:** `tests/test_issue_refiner_form.py::test_the_flag_emits_every_missing_section_as_a_finding`
