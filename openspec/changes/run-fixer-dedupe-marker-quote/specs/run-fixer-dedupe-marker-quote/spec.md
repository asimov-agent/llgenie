# run-fixer-dedupe-marker-quote

## ADDED Requirements

### Requirement: the dedupe search must find a marker whose workflow name contains a double-quote

The run-failure reactor MUST dedupe on the body marker `WORKFLOW/JOB@SHORTSHA` even when the
workflow display name itself contains a `"` character. GitHub's issue-search phrase cannot contain a
nested double-quote, so the exact `"<marker>" in:body` query must instead be built from the marker
with `"` characters removed — GitHub's index treats the quotes as separators, so the phrase still
matches the marker exactly as it was written in the body.

WHEN `filed(repo, marker)` builds the `--search` query for a marker that embeds a double-quote
THEN the query phrase carries no `"` and returns the issue whose body holds that marker

#### Scenario: a workflow name with an embedded quote is found by the stripped phrase

- **Given** an OPEN run-fixer issue whose body marker is
  `<!-- run-fixer: ci-verdict — … and says "no verdict" out loud/judge@05185f9aecc9 -->`
- **When** `filed()` is asked whether that marker exists
- **Then** it sends `gh issue list --search '"…no verdict out loud/judge@05185f9aecc9…" in:body'`
  (no `"` inside the phrase) and returns true, so no duplicate issue is filed

### Requirement: the dedupe never matches when the phrase is broken by an embedded quote

The search query MUST NOT be built by wrapping a `"`-containing marker verbatim: such a phrase
never matches (GitHub cannot nest quotes), which is the defect this change fixes. `filed()` MUST strip
every `"` out of the marker before quoting it.

WHEN `filed()` is called with a marker that contains a double-quote
THEN the emitted `--search` phrase contains no double-quote

#### Scenario: the emitted phrase never branches on the inner quote

- **Given** a marker whose workflow display name contains `says "no verdict" out loud`
- **When** `filed()` builds the query
- **Then** the `--search` argument is `"…says no verdict out loud…" in:body` — a single phrase with
  no embedded quote — and the pre-existing issue is found, filing nothing extra
