# 2026-10-31 — the no-skip guard states ONE contract, and it fails the run

Issue: [#1110](https://github.com/asimov-agent/llgenie/issues/1110) (duplicate report
[#1121](https://github.com/asimov-agent/llgenie/issues/1121) was closed into it)

## What the file said, and what it did

`tests/conftest.py` carried two guards against silent skips that disagreed about `xfail`:
`pytest_report_teststatus` failed every skipped report (so an `xfail` reddened), while
`pytest_runtest_logreport` exempted `wasxfail`. One hook said xfail was tolerated, the other forbade
it — the rule existed in two places with two answers, and a lane and a planner spent two rounds
arguing over `strict=True` about a marker the tree effectively banned.

Measuring it to write the regression test found the worse half. **The guard never failed the run.**
Mutating `report.outcome` only changes what the terminal prints; pytest computes its exit status from
its own failure counter. Measured on `main@864fffaa` in `llgenie/test:latest`:

```
$ python -m pytest tests/zzz_probe_skip.py -q     # a plain pytest.skip()
EXIT=0
F                                                                        [100%]
TEST SKIPPED — no skips allowed (AGENTS.md). …
FAILED tests/zzz_probe_skip.py::test_plain_skip
1 failed in 0.02s
```

A plain skip, an `xfail` and a module-level `skipif` all exited 0 — the "no skips, ever" guarantee was
decorative, while AGENTS.md claimed the hooks turn a skip into a failure in the exit code.

## Decisions

- **`xfail` is a skip.** A green gate must mean every test ran and passed; there is no "known failure"
  bucket in the hermetic gate. The replacement for a tracked defect is a test that asserts the defect's
  CURRENT behaviour, so the fix reds the test and its deletion is forced mechanically, not remembered.
  An "expected failure" registry was considered and rejected — a second mechanism where the inverted
  assertion needs none.
- **One predicate.** `_skip_violation(report)` is the only place that decides; both hooks ask it, so an
  exemption added to one hook alone is measurable.
- **The exit status is the contract.** `pytest_sessionfinish` turns a recorded violation into exit 1 —
  the report mutation alone cannot, whatever pytest version runs.
- **The contract is documented where a lane looks**: `docs/TESTING.md` (linked from `README.md`). The
  same paragraph in `AGENTS.md` is deferred to
  [#1143](https://github.com/asimov-agent/llgenie/issues/1143) — AGENTS.md is an agent-instruction
  file whose write needs an owner approval an unattended run cannot obtain.

## Verified

- `tests/test_no_skip_guard.py` (14 cases) loads the repository's real `tests/conftest.py` by path,
  drives each hook on its own, and runs real pytest sub-processes for `xfail`, `pytest.skip()`, a
  module `skipif` (each exits non-zero, naming the test) and a clean file (exits 0).
- **Sabotage, both hooks**: with `wasxfail` exempted in `pytest_runtest_logreport` the suite goes RED
  with `AssertionError: pytest_runtest_logreport exempted an xfail — the two no-skip hooks disagree
  again (issue #1110)`; with the exemption in `pytest_report_teststatus` it goes RED naming that hook.
  Restored → 14 passed, exit 0.
- **Sabotage, the exit status**: before `pytest_sessionfinish` existed the end-to-end case failed with
  `an xfail run stayed green (exit 0) while printing a failure` — the test has been seen red.

## Status

OpenSpec change `no-skip-guard-one-contract`; branch `fix/1110-conftest-hooks-agree`. Gates:
`make test-unit`, `make ci-unit`, `make check-docs`, `make check-wiring`,
`make openspec-validate NAME=no-skip-guard-one-contract`.
