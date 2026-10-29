# 2026-10-29 — issue #934: the change index is one row per file, not one shared table

## What was wrong

`CHANGES.md` was a single flat table and every PR prepended a row to it. That is a single append
point: two changes in flight always edit the same file at the same line, so every merge re-dirties
every other open PR, and a `DIRTY` PR gets **no CI run at all** — verified work parked behind a
one-row table edit. Measured on `main@97a24063` (2026-10-29T04:31Z): 31 open PRs, **20 `DIRTY`**;
the rebase lane's 04:02Z sweep had taken nine PRs to `MERGEABLE` onto `20f6f6b1`, then eight commits
landed and the whole set went `DIRTY` again.

## The design (and the candidates it beat)

**Chosen: the towncrier fragment shape.** The index row for a change is its own file,
`docs/changes.d/<note-stem>.md`, holding exactly one row. `CHANGES.md` is *rendered* from those
fragments by `make changes-index` (`scripts/changes_index.py`) and no change PR edits it.

- **Derive the table from `agent-wiki/` frontmatter** — rejected. It removes the append point only
  if `CHANGES.md` stops being committed, and a gitignored `CHANGES.md` makes the README's link a
  404 on GitHub. Committed-and-required-current re-creates the conflict (every PR must re-render
  the same file), and committed-and-derived removes the row a reader compares against a note, so
  "a row names a note that does not exist" can no longer be a defect — the gate would lose one of
  its three behaviours.
- **Group by month (#682), newest group's row inserted by a script** — rejected as a fix for *this*
  issue, kept as its own issue. Grouping shortens the append point (one month's file) but does not
  remove it: every PR landing in the current month still edits that month's first line, so the
  conflict is monthly instead of always. #682 is legibility, and it composes with this change: the
  renderer in `scripts/changes_index.py` is where a per-month grouping would live, reading the same
  fragments.
- **Row written at merge time by the merge lane** — rejected for now. The issue records five open
  PRs touching `.github/workflows/auto-merge.yml` (#918, #915, #909, #898, #916); a sixth builder on
  that file would serialize exactly as badly as the table did, and a row that exists only after a
  merge is invisible to the gate that runs on the PR.

## What changed

- `scripts/changes_index.py` — `check` / `render` / `write` / `report` over `docs/changes.d/`.
  `check` reds on a note with no fragment, a fragment whose note is gone, a fragment that is not
  exactly one well-formed row, and a fragment indexing a note that is not its own name.
- `Makefile` — `make changes-index` (render + write) and `make changes-index-report`; `check-docs`
  now runs `changes_index.py check` first, so the gate that already ran in `ci-unit` covers the new
  shape. Both targets are in `.PHONY` and documented in `README.md`.
- `scripts/check_docs.py` — the index it checks is the fragment directory: note → its own row
  (missing reds), row → an existing note (dangling reds), row shape, plus the existing `CHANGES.md`
  dangling-link check and the README → `CHANGES.md` link.
- The 217 rows already in `CHANGES.md` were split, verbatim, into 217 fragments by a script; the
  diff of the data rows is empty (`git show HEAD:CHANGES.md | grep '^| 20'` vs the rendered file
  differ only in within-date order, which is now deterministic by note name). `make changes-index`
  reproduces `CHANGES.md` exactly (`changes-index-report`: `217 row(s) committed, 217 rendered —
  current`).
- Docs: `README.md` (the `CHANGES.md` row, and the docs-gate block naming both new targets),
  `docs/ARCHITECTURE.md` (the `docs/` row, the `CHANGES.md` row, the `agent-wiki/` census, the
  `check-docs` paragraph, the report-target lists), and the `CHANGES.md` header itself.

## Conflict impact

Under the new scheme a change PR touches `agent-wiki/<note>.md` and `docs/changes.d/<note>.md` —
both new files with unique names — and nothing else in the index. Two changes can add both files
with no shared line, so **zero open PRs are re-dirtied by the next merge**, where the old scheme
re-dirtied every open PR that had a row. Proven structurally rather than asserted: two scratch
branches each adding a note + fragment merge with `git merge-tree` reporting no conflict (the same
method the issue used to measure the 20 `DIRTY` PRs).

## Known follow-up

`AGENTS.md`'s "Documentation is part of the change" item 2 still says a change adds its row to
`CHANGES.md`. That file is protected from this run's writes, so the wording update is filed as its
own issue, **#942**, linked from PR #934 — the rule the gate enforces is the fragment row, and the
README, `docs/ARCHITECTURE.md` and `CHANGES.md` all state it.

## Verified

- `make check-docs` — red on a removed note (it names the missing fragment), red on a fragment
  naming a note that is gone, green once restored (`tests/test_check_docs.py`,
  `tests/test_changes_index.py`, in `make test-unit`).
- `make lint check-wiring check-workflows check-pr-hygiene check-issue-bodies check-pr-authors`.
