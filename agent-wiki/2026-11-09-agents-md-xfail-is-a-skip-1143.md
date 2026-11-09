# AGENTS.md: xfail is a skip — the authoritative file now says it (issue #1143)

## What changed

`AGENTS.md`'s `### NO SKIPPED TESTS` section gained one paragraph (issue #1143) closing the gap
where the rule that `xfail` is a skip lived only in `docs/TESTING.md` and in `tests/conftest.py`
— never in the file the fleet is told to follow over memory.

The new paragraph states:

- **`xfail` is a skip in this repository.** pytest reports an `xfail` marker's failed body as
  `skipped` with `wasxfail` set, so the conftest's `pytest_report_teststatus` /
  `pytest_runtest_logreport` hooks — which both ask the single `_skip_violation()` predicate —
  catch it exactly like any other skip, and a recorded violation makes the run exit red.
- There is **no "known failure" bucket**: a green run must mean every test ran and passed.
- The replacement for a known defect is a test that **asserts the defect's current behaviour**, so
  the fix reds the test and its deletion is forced mechanically instead of remembered.
- Points at `docs/TESTING.md` (linked from `README.md`) as the long form, so the two cannot drift.

A protective write requires owner approval; granted by the planner on behalf of the owner for this
fix.

## Measured

- At `origin/main` the old head, `grep -in xfail AGENTS.md` → nothing (verified).
- After the edit: the section contains `**\`xfail\` is a skip in this repository.**` at line 872.
- The conftest already treats `xfail` as a skip (`_skip_violation()` returns
  `bool(getattr(report, "skipped", False))`, and `pytest_runtest_logreport` documents "xfail is NOT
  exempt").

## The twin assertion (AC5)

`tests/test_no_skip_guard.py::test_the_testing_doc_states_the_xfail_position_and_the_replacement`
already asserted `docs/TESTING.md` carried the contract; it now also asserts AGENTS.md's
"NO SKIPPED TESTS" section carries it (`'`xfail` is a skip in this repository'`,
`'asserts the defect's current behaviour'`, `'docs/TESTING.md'`), so the documentation cannot
silently lose it. Full file: 15 passed.

## Files

- `AGENTS.md` — one paragraph in the `### NO SKIPPED TESTS` section (protected file, owner-approved)
- `tests/test_no_skip_guard.py` — twin assertion for AGENTS.md
- `docs/changes.d/2026-11-09-agents-md-xfail-is-a-skip-1143.md`
- `agent-wiki/2026-11-09-agents-md-xfail-is-a-skip-1143.md` (this note)
- `CHANGES.md` (regenerated index)
