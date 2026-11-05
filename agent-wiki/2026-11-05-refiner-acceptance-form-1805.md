# Refiner flags a hand-authored issue without the acceptance form (#1805)

`scripts/issue_refiner.py` — the refiner that keeps the backlog implementable on spare capacity —
previously read a hand-authored issue body and passed it to the review agent verbatim, whatever its
shape. Under #1796 #3 ("hand-authored issues … carry the acceptance-criteria form") that was a gap:
a hand-authored body that lacks a tickable `## Acceptance criteria` section (or any section) reached
the `/ refine` surface without anyone saying so, so the form never landed and the issue could stay
unimplementable. #1804 closed the PR-body half; this is the issue-side half.

## Change

`issues_refiner.render()` — the function that builds the agent's input `refine-in.md` (the `/ refine`
endpoint) — now calls `issue_body.missing()` on the source body (via the new
`acceptance_form_flag()` helper) and, when it finds shape defects, appends an
`## Acceptance-criteria form (issue #1796 #3)` finding block listing **every** `missing()` defect.
The review agent is then told to include a canonical `## Acceptance criteria` section with tickable
`- [ ]` checkboxes in its `RESTATED:` spec, so "done" is a list a reviewer can tick.

- **Reuses, never restates** — the finding is `issue_body.missing()`'s own text, imported; the refiner
  never duplicates or paraphrases the reader, and never edits a human's issue body (its standing
  rule).
- **Emission of a finding, not content fabrication** — the flag names the defect; it does not invent
  criteria that are not in the source (`- [ ]` lines come only from the agent's restatement).
- **Byte-identical on conforming bodies** — when `issue_body.missing()==[]` (a producer-rendered
  issue) nothing is emitted; the refiner does not re-render what already conforms (#1796).

## Tests (red-on-old / green-on-fixed)

`tests/test_issue_refiner_form.py` — 4 new tests: conforming body → `render()` output unchanged (no
flag); hand-authored body with a `## Acceptance criteria` heading but no checkbox → the endpoint
carries the `## Acceptance-criteria form (issue #1796 #3)` finding naming the exact defect; a
one-section body → every missing section is named; empty/conforming boundary. On the pre-#1805 tree
the behavior tests fail (`AttributeError: no attribute 'acceptance_form_flag'`); on this tree all 4
pass alongside the 22 existing `test_issue_refiner.py` (26 total). Change-note trio (#1123) +
`docs/BOTS.md` row + `CHANGES.md` regen (`make changes-index`).
