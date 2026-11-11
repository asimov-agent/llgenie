# Test-suite aggregation: discover, never enumerate

A hand-written test-file list on one `make` recipe line is the most
conflict-prone line in the tree: two unrelated PRs that add tests fight over it,
and a name lost resolving the conflict silently stops running. The sibling repo
`trending-local-llms` solves this by *computing* the suite. Replace the
enumerated recipe with an aggregating script (`scripts/unit_tests.py`) that
discovers every `tests/test_*.py` and runs the selection, so the `make` recipe
names NO test file. This is the high-signal fix for the "new test file is
invisible until a make target names it" trap.

## Rules

- **A new test file joins the gate the moment it exists.** Discovery means no
test is ever invisible because nobody added its name to a list.
- **Keep deliberately-gated-out files in a dated exclusion roster** — a JSON
fixture recording each file's reason, issue, date, and the target that runs it
in its place. *Keeping a file out* becomes a recorded decision, not an accident
of omission.
- **Fail closed on a broken roster.** A missing/corrupt roster must be a LOUD
failure, never a silent empty selection — an empty suite passes green and
proves nothing.
- **De-select by exact node id** (`--deselect file::test`), never a `-k`
expression. `-k` matches substrings, so a new test whose name CONTAINS a
deselected test's name is silently dropped from the gate. Exact ids cannot.
- **Wire the guard through the aggregator.** Make `check-wiring` ask the
aggregator what it selects, so a discovered file is still proven wired through
the target that runs it.
- **Prove the refactor moves the list, not the gate.** Assert the aggregator's
selection is byte-identical to the old enumerated list before calling it done
(here: 74/74 files reproduced exactly).
- **Tests that assert a file "runs in the gate" must read the aggregator's
selection**, not re-parse the recipe line — otherwise they pin the shape you
just removed.

The model for computing rather than enumerating is `trending-local-llms`'s
`scripts/run_tests.sh`: it discovers `tests/test_*.py` by glob and runs each in
its own process, no hand-maintained list.
