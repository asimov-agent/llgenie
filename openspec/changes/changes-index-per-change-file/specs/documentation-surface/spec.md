## ADDED Requirements

### Requirement: the change index is one row per file

The index of change records MUST be a directory of one-row files, not one shared table: each change
owns `docs/changes.d/<note-stem>.md`, which holds exactly one row — a date, a one-line summary, a
link to `agent-wiki/<note-stem>.md`, and an issue/PR reference. No two changes write the same file,
so a merge cannot re-dirty an open PR.

WHEN a change lands
THEN it has added its note and its own fragment, and touched no shared index file.

#### Scenario: two changes in flight merge without a conflict
Given two branches that each add a note and a fragment of their own,
When   they are merged with `git merge-tree`,
Then   the result is one tree sha with no conflicted path.

- **Test:** `tests/test_changes_index.py::test_the_real_tree_indexes_every_note_with_no_defect` and
  the `merge-tree` proof recorded in the PR body (real `git merge-tree` over two scratch branches
  that each add a note + fragment).

#### Scenario: a note with no row is red, and its own row file is the fix
Given a note in `agent-wiki/` whose `docs/changes.d/` row does not exist,
When   `make check-docs` runs,
Then   it fails naming the note and the fragment path the change owes,
And    adding that one file makes it pass.

- **Test:** `tests/test_changes_index.py::test_a_note_without_a_row_is_red_and_adding_its_row_is_green`

#### Scenario: a row naming a missing note is red, and restoring the note is green
Given a fragment whose note has been deleted,
When   `make check-docs` runs,
Then   it fails naming the fragment and the note that does not exist,
And    restoring the note makes it pass.

- **Test:** `tests/test_changes_index.py::test_deleting_a_note_reds_the_gate_and_names_it_then_restoring_is_green`

### Requirement: a fragment is exactly one well-formed row for its own note

A fragment MUST hold exactly one line, that line MUST parse as
`| date | summary | [note](agent-wiki/<stem>.md) | #issue |`, its date MUST be `YYYY-MM-DD`, its
`Issue / PR` cell MUST name an issue or PR, and it MUST index the note of its own name.

WHEN a fragment is malformed
THEN `make check-docs` fails naming the fragment and the shape it broke.

#### Scenario: five malformed shapes each fail loudly
Given a fragment with two rows, one that is not a row, one with no issue reference, one with a
non-`YYYY-MM-DD` date, and one indexing somebody else's note,
When   `make check-docs` runs,
Then   each fails naming the fragment file.

- **Test:** `tests/test_changes_index.py::test_a_row_may_not_index_a_note_of_another_name` and
  `tests/test_check_docs.py::test_a_malformed_index_row_fails`

### Requirement: CHANGES.md is rendered from the fragments, never hand-merged

`CHANGES.md` MUST be rendered from `docs/changes.d/` by `make changes-index`
(`scripts/changes_index.py`), newest first and deterministic, and it MUST keep being committed and
linked from `README.md`. A change PR MUST NOT edit it; the documentation lane refreshes it, and
`make changes-index-report` states how far behind it is.

WHEN the fragments change
THEN `make changes-index` rewrites `CHANGES.md` to exactly the rendered table, and rendering twice
produces byte-identical output.

#### Scenario: the committed table is the renderer's output
Given the real checkout,
When   `changes_index.py render` runs,
Then   its output equals the committed `CHANGES.md`.

- **Test:** `tests/test_changes_index.py::test_the_real_index_renders_the_committed_changes_md`

#### Scenario: the gate still fails when the README cannot reach the index
Given a README with no link to `CHANGES.md`,
When   `make check-docs` runs,
Then   it fails saying the README does not link the index.

- **Test:** `tests/test_check_docs.py::test_the_readme_must_link_the_change_index`
