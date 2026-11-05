# refiner-acceptance-form — proposal

Issue: [#1805](https://github.com/asimov-agent/llgenie/issues/1805)

## Why

Under the owner's universal form rule (#1796 #3) every issue a fleet lane files AND every PR body
it opens must carry a `## Acceptance criteria` section with tickable `- [ ]` checkboxes. #1804
landed the PR-body half; the issue-refiner half was never connected: `scripts/issue_refiner.py`
reads a hand-authored issue body and hands it to the review agent verbatim, whatever its shape. A
hand-authored issue that lacks the acceptance form is silently accepted on the `/ refine` surface —
`render()`, which writes the agent's `refine-in.md`, never calls `issue_body.missing()` — so the
form never lands and #1796 #3 stays un-tickable on the issue side.

## What Changes

- `issue_refiner.render()` calls `issue_body.missing()` on the source body via a new
  `acceptance_form_flag()` helper and, when it finds shape defects, appends an
  `## Acceptance-criteria form (issue #1796 #3)` finding block naming every defect, telling the
  review agent to include a canonical `## Acceptance criteria` section with `- [ ]` checkboxes in
  its `RESTATED:` spec.
- The finding reuses `issue_body.missing()` verbatim (never restated), never edits a human's issue
  body, and never fabricates `- [ ]` criteria that are not in the source.
- A producer-rendered (already-conforming) body (`missing()==[]`) passes through byte-identical —
  no re-render of a conforming body (#1796).
- 4 new tests (`tests/test_issue_refiner_form.py`), red-on-old / green-on-fixed; change-note trio
  (#1123) + `docs/BOTS.md` row + `CHANGES.md` regen.

## Out of scope

- The PR-body acceptance gate (#1804, ci-pipelines) and its enforcement gap (#1807).
- #1802/#1800 tracks, serve/engine behavior, #1088 merge.
- Per-lane skill text propagation (#791) / SYNC — the fleet half.
