# guard-write-level-arm — proposal

Issue: [#306](https://github.com/asimov-agent/llgenie/issues/306)

## Why

`tests/test_workflow_guards.py::test_the_guard_checks_both_actors_and_a_write_level` is the rule that a
guard accepts a **write level and nothing weaker**. As shipped by #300 it could not fail for the case it
exists to catch:

```python
joined = "\n".join(guards)
if not all(level in joined for level in ALLOWED_PERMISSIONS):
    weak.append(...)
```

A substring check for `admin`, `maintain` and `write` is satisfied by **any** guard text that happens to
contain those three words — so `admin|maintain|write|read` passes it. Measured on `main` (`ed75b87`),
with `.github/workflows/issue-bot.yml`'s case arm widened to `admin|maintain|write|read`:

```
FAILED tests/test_workflow_guards.py::test_every_guard_step_is_byte_identical
1 failed, 5 passed
```

The byte-identity rule caught it; the write-level rule did not. #295 exists because four guards accepted
**any** collaborator level via a `curl` `204`, and the rule that replaced it is enforced by a test a
substring match satisfies — the "a guard that bounds a set must derive that set" failure class. The next
person who edits the arm, or a new workflow whose guard is hand-written, gets no signal.

## What Changes

- **The accepted set is read from the guard's own `case` arm.** New `_accepted_levels(run)` parses the
  `case` pattern(s) (`admin|maintain|write)`) out of the guard's `run` step and returns the words they
  accept; an arm whose line also `exit`s is the refusal arm and is skipped. The rule is now
  `accepted == {admin, maintain, write}` exactly, so adding `read`, `triage` or a bare `*` arm fails and
  names the workflow.
- **New `_guard_runs(path)`** reads the guard step's own `run` text, not the whole job's step text — so
  the `204` check cannot be tripped by an unrelated step that happens to mention `204`.
- **The negative direction is proven in the suite.**
  `test_the_write_level_rule_reads_the_decision_not_the_prose` widens the real arm to
  `admin|maintain|write|read` and `…|read|triage` (which the old substring check PASSES, asserted), and
  shows the arm reader rejects them; it also rejects `read`, `triage` and `*` arms.
- **Only the test changes.** No file under `.github/workflows/**` is touched — the eleven guard bodies
  are already byte-identical from #300.

## Not covered

- Rewriting the guard bodies: out of scope by the issue's own "Not covered", and unnecessary — they are
  byte-identical (#300).
- #254 (the `macos-15-intel` queue) — a repo-settings/hosted-runner decision, unchanged by this.

Refs: #295 (the audit that shipped the guard), #122 (the guard's origin), #300 (the PR that normalized
the eleven bodies and filed this finding).
