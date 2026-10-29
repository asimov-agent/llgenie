# Design — why one row per file, and not the other shapes (issue #934)

## Chosen: towncrier fragments, one row per file

`docs/changes.d/<note-stem>.md` holds exactly one row; `CHANGES.md` is rendered from the fragments.

The property that matters is **mathematical, not stylistic**: a set of changes can only avoid a
conflict in one file if no two of them write the same file. Every shape below either keeps one
shared row file or loses a gate behaviour; only fragments have both zero shared writes and a
row a gate can compare against a note.

`CHANGES.md` stays committed because `README.md` links it and a reader opens it on GitHub. It is a
**rendered** artifact: `make check-docs` does not require it to be current, so a change PR never has
to touch it, and `make changes-index-report` prints how many rows it is behind. The documentation
lane runs `make changes-index`; that is the one writer.

## Rejected: generate the table from `agent-wiki/` frontmatter

Attractive because a change would add one file, not two. It fails on the gate, not on the merge:

- **gitignored output** (the only shape with zero shared writes if the table stays derived): the
  README's `CHANGES.md` link 404s on GitHub, so the user-facing index is gone.
- **committed and required current**: every PR must re-render the same file, which re-creates
  exactly the append point this issue exists to remove — every merge re-dirties every open PR.
- **committed and derived-but-unchecked**: rows are generated from notes, so "a row names a note
  that does not exist" becomes impossible to observe, and one of the gate's three behaviours is
  lost. Deleting a note simply deletes its row.

The fragment keeps a row a human wrote in the tree, so both directions stay falsifiable: a note can
exist with no row (red), and a row can exist with no note (red).

## Rejected: group by month (#682), newest group's row inserted by a script

Grouping shortens the append point to one month's file. It does not remove it: every PR landing in
the current month still edits that month's first line, so the conflict is monthly instead of
always, and the issue's measurement (16 of 19 `DIRTY` PRs conflicted on `CHANGES.md` alone) recurs
inside each month. #682 is legibility — a reader scanning what changed in the release they run — and
it composes with this change: `scripts/changes_index.py::render` is the one place a per-month
grouping would be added, reading the same fragments.

## Rejected: the row written at merge time by the merge lane

A row that exists only after the merge is invisible to the gate that runs on the PR, so the index
cannot be checked before landing. It also adds a writer to `.github/workflows/auto-merge.yml`, which
already had five open PRs against it (#918, #915, #909, #898, #916) — a sixth builder on one file
serializes exactly as badly as the table did.

## Migration

The 217 rows in `CHANGES.md` were split verbatim into `docs/changes.d/<note-stem>.md` by a script:
each fragment holds the row's exact original text. The rendered file differs only in header prose
and within-date ordering (now deterministic: date desc, then note name). A row is never rewritten by
this change (issue #934, `## Not in scope`).

An open PR that still carries a `CHANGES.md` row converts on rebase: drop the `CHANGES.md` hunk, add
`docs/changes.d/<note-stem>.md` with that row. Nothing else in its diff changes.
