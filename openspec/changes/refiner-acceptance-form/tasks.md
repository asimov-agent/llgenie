# refiner-acceptance-form — Tasks

Issue: [#1805](https://github.com/asimov-agent/llgenie/issues/1805)

- [x] 1. `issue_refiner.render()` emits an `## Acceptance-criteria form (issue #1796 #3)` finding (via `acceptance_form_flag()`) when `issue_body.missing()` finds shape defects in a hand-authored body; a conforming body passes byte-identical.
- [x] 2. The finding reuses `issue_body.missing()` verbatim (never restates the reader, never edits a human's issue body, never fabricates `- [ ]` criteria).
- [x] 3. `tests/test_issue_refiner_form.py` (4 tests) are red-on-old / green-on-fixed; the 22 existing `test_issue_refiner.py` still pass (26 total).
- [x] 4. Change-note trio (#1123) + `docs/BOTS.md` row + `CHANGES.md` regen; `make check-docs` / `lint` / `check-issue-bodies` green.
- [x] 5. `make openspec-validate NAME=refiner-acceptance-form` exits 0.
