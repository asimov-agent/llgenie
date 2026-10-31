# no-skip-guard-one-contract — proposal

Issue: [#1110](https://github.com/asimov-agent/llgenie/issues/1110) (the duplicate report was
[#1121](https://github.com/asimov-agent/llgenie/issues/1121), closed into it)

## Why

`tests/conftest.py` carried TWO guards against silent skips and they disagreed about `xfail`:

```
tests/conftest.py:63  pytest_report_teststatus   if report.skipped: report.outcome = "failed"      # no exemption
tests/conftest.py:76  pytest_runtest_logreport   ... if not report.wasxfail: report.outcome = ...  # exempts it
```

One hook said "a skip is a violation" (xfail included), the other said "a non-xfail skip is". A lane
that added an `@pytest.mark.xfail` for a tracked defect read the file and could not tell which rule
was real; two rounds of a planner and an implementer argued over `strict=True` about a marker the
tree effectively forbade. A rule that lives in two places, with two answers, is the defect.

Measuring the guard to write its regression test turned up a worse one: **the guard never failed the
run at all**. Mutating `report.outcome` changes only what the terminal prints — pytest computes its
exit status from its own failure counter — so a skipped test printed `FAILED` and the process still
exited 0:

```
$ docker run ... llgenie/test:latest python -m pytest tests/zzz_probe_skip.py -q   # main@864fffaa
EXIT=0
F                                                                        [100%]
TEST SKIPPED — no skips allowed (AGENTS.md). …
FAILED tests/zzz_probe_skip.py::test_plain_skip
1 failed in 0.02s
```

The "no skips, ever" guarantee was decorative: a plain skip, an `xfail`, and a module `skipif` all
exited green. AGENTS.md states the opposite — "the conftest … hooks turn any skipped test into a
failure in the exit code".

## What Changes

- **One contract, written in the file.** A paragraph above the hooks states what a SKIP is (any
  report pytest marks `skipped`, in any phase: `pytest.skip()`, `skipif`, a conditional skip, or an
  `xfail` whose test failed), that an XFAIL is **not** an exemption, and which hook owns which phase.
- **`xfail` is a violation.** The tree has no "known failure" bucket in the hermetic gate: a green
  gate must mean every test ran and passed. The replacement for a tracked defect is a test that
  asserts the defect's CURRENT behaviour, so the fix reds that test and its deletion is forced
  mechanically rather than remembered. `docs/TESTING.md` (linked from `README.md`) states it for the
  lane planning a test; an "expected failure" registry was considered and rejected as a second
  mechanism where the inverted assertion needs none.
- **One shared predicate.** Both hooks ask `_skip_violation(report)` — the only place that decides
  what a violation is. A future edit cannot split them without editing the predicate itself, and a
  hook that stops asking it is caught by a test that drives each hook on its own.
- **The exit status is the contract.** `pytest_sessionfinish` turns a recorded violation into exit 1,
  so a skip is red whether or not a report mutation reaches pytest's counter. The per-test `FAILED`
  line and a `NO-SKIP GUARD: N skipped test(s) …` line name the tests.
- **A regression test that has been seen failing** — `tests/test_no_skip_guard.py` drives each hook
  in isolation (an `xfail` in either hook goes red naming that hook) and runs real pytest
  sub-processes for `xfail`, `pytest.skip()`, a module `skipif` (red, non-zero exit) and a clean run
  (green).

## Benefit

A lane reads one paragraph and knows the rule, and the rule is enforced by the exit status instead of
by a printed line. An `xfail` smuggled into the hermetic gate fails the build and names the test; a
prerequisite that silently vanishes can no longer pass CI while reporting green. The next person who
tries to exempt `xfail` in one hook is told by a red test which hook they broke.

## Not covered

- **The same paragraph in `AGENTS.md`'s "NO SKIPPED TESTS" section** — `AGENTS.md` is an
  agent-instruction file whose writes need owner approval, which an unattended run cannot obtain. The
  rule lands in `docs/TESTING.md` (linked from `README.md`) and in the conftest comment until that
  mirror is written. Filed as [#1143](https://github.com/asimov-agent/llgenie/issues/1143).

## Technical

- `tests/conftest.py`: `_skip_violation()` (the shared predicate), `_skip_violation_message(hook)`,
  `_SKIP_VIOLATIONS` (run-scoped ledger), `_fail_report()`, and `pytest_sessionfinish()` beside the
  two hooks; the contract paragraph above them.
- `tests/test_no_skip_guard.py` (new, discovered by `make test-unit` — no roster edit): each hook ×
  (`xfail`, plain skip, passing report), the setup-phase ownership of `pytest_report_teststatus`, the
  shared predicate, `pytest_sessionfinish` on a recorded violation / a clean run, and four real
  subprocess runs driven through a throwaway conftest that re-exports the repo's own hooks by path.
- `docs/TESTING.md` (new, linked from `README.md`) — the no-skip contract, the xfail position, and the
  tracked-defect pattern with its mechanical removal; `README.md`'s reference table gains its row.
- `agent-wiki/2026-10-31-no-skip-guard-one-contract.md` + `docs/changes.d/<stem>.md`.
- Gates: `make test-unit` (the new file is inside it), `make ci-unit`, `make check-docs`,
  `make openspec-validate NAME=no-skip-guard-one-contract`.
