# llgenie unit-suite aggregation

The hermetic unit gate is aggregated, never enumerated — `make test-unit` runs
`python scripts/unit_tests.py run`, which DISCOVERS `tests/test_*.py` minus the
roster `tests/fixtures/unit-suite.json`.

## The model

- **A new `tests/test_*.py` needs NO Makefile edit.** Discovery picks it up;
  `make check-wiring` proves every file the aggregator selects is wired to the
target that runs it, so a file `main` gains just becomes one more selected file
(0 unaccounted).
- **A deliberate exclusion goes in the roster**, each entry carrying a reason,
an issue, the date, and the target that runs that suite instead — never by
deleting a name from a recipe.
- The same `-k`-style de-selections of live release reads are stored as exact
  `--deselect` node-ids in the roster, so a test that used to read a `-k`
  expression instead asserts the aggregator's `argv()` returns that node-id.

## `ci-openspec` fails a change with unticked tasks

CI's `linux / openspec` job is `make openspec-validate NAME=ci-pipeline` PLUS
`make openspec-tasks-check`, and the tasks check fails ANY active
`openspec/changes/*` dir that has an unchecked `- [ ]` line. A red ~16s
`openspec` job while every other stage passes means a change's `tasks.md` was
left unticked — not a spec defect. Reproduce the gate in seconds on the host
with `make openspec-tasks-check` (pure python, no container). Tick each task
the moment its work is verified and before the first push.

The checklist is also the record of what changed: when the full suite run finds
more sites than you planned ("7 self-wiring assertions" was really nine), rewrite
the task text to match the evidence before ticking — never leave a stale count.

## Self-referential assertions break when selection changes

Switching a suite's selection (explicit list to discovery, `-k` expression to
node-id) breaks the suite's OWN tests that lock the old mechanism: tests that
assert their own file name appears in the recipe, or read the `-k` expression.

- Grep the whole test tree for the old shape FIRST, then run the FULL suite —
  some sites assert a *different* shape than the one you grepped
  (file-name-in-Makefile-text vs exact `--deselect` argv), so grep alone misses
them. The full run found two extra sites beyond the seven located by grep.
- A site that asserts its file name is `in` the whole Makefile text breaks on
  ANY match in the file, not just the line you changed — sweep for every instance
  of that assert class before the long run.
