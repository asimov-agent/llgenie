# The change index is one row per file, rendered into CHANGES.md (issue #934)

## Why

`CHANGES.md` was a single flat table and every PR prepended a row to it. That is a single append
point, so every merge re-dirtied every other open PR: measured 2026-10-29 at `main@97a24063` while
this change was designed, 10 of the 12 open PRs the platform read `DIRTY` conflicted on
`CHANGES.md`; the planner's earlier measurement that morning was 20 `DIRTY` of 31 open, 16 of them
`CHANGES.md`-only. `git merge-tree` on the currently-DIRTY set is the measurement.

A `DIRTY` PR gets no CI run at all, so the cost is not a slow review: verified work cannot receive a
verdict. The rebase lane repaired nine PRs at 04:02Z onto `20f6f6b1`; eight commits landed and the
whole set went `DIRTY` again. That is a serialization defect in the change-record convention, not a
rebase problem — the repair was correct and the structure guaranteed it would be undone.

## What Changes

- **`docs/changes.d/<note-stem>.md` — one index row per file.** A change adds its note
  (`agent-wiki/<stem>.md`) and one fragment holding exactly one row. Two changes add two different
  files, so git has nothing to conflict on.
- **`CHANGES.md` is rendered**, not hand-edited: `scripts/changes_index.py` renders it from the
  fragments and `make changes-index` writes it. No change PR touches it; the documentation lane
  refreshes it.
- **The gate's three behaviours survive**, measured against the fragment directory and the rendered
  file: a note with no row reds (naming the row it owes), a row naming a missing note reds (naming
  the note), a malformed row reds, and `README.md` must still link `CHANGES.md`.
- **The 217 existing rows are preserved** by splitting them verbatim into 217 fragments; the
  rendered `CHANGES.md` differs from the old file only in its header prose and in within-date
  ordering, which is now deterministic (date desc, then note name).

Candidates rejected, and why, are recorded in `design.md`.

## Impact

- Affected specs: `documentation-surface` (the index is a directory; the render target; the gate's
  three behaviours).
- Affected code: `scripts/changes_index.py` (new), `scripts/check_docs.py` (index source),
  `Makefile` (`check-docs`, `changes-index`, `changes-index-report`), `tests/test_changes_index.py`
  (new), `tests/test_check_docs.py`, `README.md`, `docs/ARCHITECTURE.md`, `CHANGES.md`,
  `agent-wiki/2026-10-29-changes-index-per-change-file.md`, `docs/changes.d/**` (218 fragments).
- Not affected: #682 (grouping by month) — it composes; the renderer is where a grouping would
  live. `AGENTS.md`'s "Documentation is part of the change" item 2 still says a change adds its row
  to `CHANGES.md`; that file is protected from this run's writes, so the wording update is filed as
  its own linked issue.
