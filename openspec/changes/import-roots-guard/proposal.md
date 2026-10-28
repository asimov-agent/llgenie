# One import root for the tests, enforced by a ratchet (issue #796)

## Why

104 test files carry their own `sys.path.insert` at `798cbee`, in seven distinct shapes, and 141 import a
`scripts/` module bare. The suite therefore has as many import roots as files, and a migration cannot be
verified by counting: a file that adds a path entry and imports nothing from it looks migrated.

## What changes

- `scripts/check_import_roots.py` refuses two shapes: a `sys.path.insert`/`append` outside
  `tests/conftest.py`, and a bare import of a module that lives in `scripts/`.
- `make check-import-roots` runs it in **ratchet** mode against
  `tests/fixtures/import-roots-baseline.json`: the count may fall as batches migrate and may never rise.
  That is what lets the guard land *before* the migration instead of red-ing the suite on its own commit.
- The baseline is recorded with `--update`, so the numbers are data in the tree, not a claim in a comment.

## What does not change

The migration itself. This change adds the guard and nothing else; batches follow, each verified on the
migrated files and their dependants.
