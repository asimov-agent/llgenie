# The write-level guard rule reads the `case` arm (#306, from #300 / #295)

## Why

`tests/test_workflow_guards.py::test_the_guard_checks_both_actors_and_a_write_level` is the rule that a
trigger guard accepts a write level and nothing weaker. It shipped from #300 as a substring check:

```python
joined = "\n".join(guards)
if not all(level in joined for level in ALLOWED_PERMISSIONS):
    weak.append(...)
```

`all(level in joined …)` is satisfied by any text containing `admin`, `maintain` and `write` — so a guard
whose `case` arm accepts `admin|maintain|write|read` passed the rule that exists to reject exactly that.

## Verified against `main@ed75b87` (before the fix)

Widening `.github/workflows/issue-bot.yml`'s arm to `admin|maintain|write|read`:

```text
FAILED tests/test_workflow_guards.py::test_every_guard_step_is_byte_identical
1 failed, 5 passed
```

Only the byte-identity rule caught it; the write-level rule passed. Same result for a `read`-only arm only
in the sense that the substring check happens to miss when the words vanish — the superset arm is the case
that mattered, and it went green.

## What landed

- `_accepted_levels(run)` parses the guard's own `case` pattern(s) (`admin|maintain|write)`) and returns
  the words they accept; an arm whose line also `exit`s is the refusal arm and is skipped.
- The rule is now `accepted == {admin, maintain, write}` **exactly**, so `read`, `triage` or a bare `*`
  fails and names the workflow.
- `_guard_runs(path)` reads the guard step's own `run` text, not the whole job's — so the `204` check
  cannot be tripped by an unrelated step that mentions `204`.
- `test_the_write_level_rule_reads_the_decision_not_the_prose` proves the negative direction in the same
  suite: it widens the REAL arm (asserting the old substring check would still pass it) and shows the arm
  reader rejects it, then rejects `read`, `triage` and `*` arms.
- **No file under `.github/workflows/**` is touched** — the eleven guard bodies are already byte-identical
  from #300.

## Verification

- `tests/test_workflow_guards.py`: **7 passed** in `llgenie/test:latest` (the fix), and against the
  widened-arm tree **2 failed, 5 passed** — the write-level rule now fails too, which it did not before.
- `make lint`, `make check-docs`, `make check-wiring`, `make openspec-validate NAME=guard-write-level-arm`.

## Note

The issue is #306, filed by #300 (which closed #295). No workflow file changes here: this is the test
hardening #306 asked for, kept in its own change.

Refs: #295 (the guard audit), #122 (the guard's origin), #300 (the PR that normalized the eleven bodies
and filed #306).
