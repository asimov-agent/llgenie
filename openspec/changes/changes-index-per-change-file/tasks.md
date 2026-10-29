# Tasks — the change index is one row per file (issue #934)

- [x] 1. `scripts/changes_index.py`: `check` / `render` / `write` / `report` over
      `docs/changes.d/<note-stem>.md` (one row per file, validated: one line, date, summary, its own
      note link, an issue/PR reference)
- [x] 2. `Makefile`: `changes-index` (render + write) and `changes-index-report`, both `.PHONY`;
      `check-docs` runs `changes_index.py check` so `ci-unit` gates the fragments
- [x] 3. `scripts/check_docs.py`: the index it checks is the fragment directory — note → its own row,
      row → an existing note, row shape — plus the existing `CHANGES.md` dangling-link check and the
      README → `CHANGES.md` link
- [x] 4. Split the 217 rows already in `CHANGES.md` verbatim into 217 fragments; regenerate
      `CHANGES.md` with `make changes-index` and confirm the data rows are unchanged
- [x] 5. `tests/test_changes_index.py` (render determinism, the two fault directions, malformed rows,
      wiring) and `tests/test_check_docs.py` updated for the new index source, including the
      delete-a-note → RED → restore → GREEN proving test
- [x] 6. Docs: `README.md` (the `CHANGES.md` row + the docs-gate block naming both new targets),
      `docs/ARCHITECTURE.md` (`docs/` row, `CHANGES.md` row, `agent-wiki/` census, `check-docs`
      paragraph, report-target lists), the `CHANGES.md` header
- [x] 7. `agent-wiki/2026-10-29-changes-index-per-change-file.md` + its own
      `docs/changes.d/2026-10-29-changes-index-per-change-file.md` fragment
- [x] 8. Verify: `make check-docs` RED with a note deleted and RED with a row naming a missing note,
      GREEN after restore; `git merge-tree` over two scratch fragment branches reports no conflict
- [x] 9. Gates: `make lint check-docs check-wiring check-workflows check-dispatch-forms
      check-pr-hygiene check-issue-bodies check-pr-authors`, `make test-unit` for the touched files,
      `make openspec-validate NAME=changes-index-per-change-file`
