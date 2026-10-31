# Tasks

- [x] `tests/conftest.py`: one contract paragraph above the hooks — what a SKIP is (any phase, any
      cause, `xfail` included), that `xfail` is not an exemption, and which hook owns which phase.
- [x] `tests/conftest.py`: `_skip_violation(report)` is the shared predicate BOTH hooks ask; no hook
      carries its own copy of the rule and neither exempts `wasxfail`.
- [x] `tests/conftest.py`: `pytest_sessionfinish` turns a recorded violation into exit 1, because a
      report mutation alone left a skipped test exiting 0 (measured at `main@864fffaa`).
- [x] `tests/test_no_skip_guard.py` (new; discovered by `make test-unit`, no roster edit): each hook ×
      (`xfail`, plain skip, passing report), the setup-phase ownership of `pytest_report_teststatus`,
      the shared predicate, and `pytest_sessionfinish` on a recorded violation / a clean run.
- [x] `tests/test_no_skip_guard.py`: real subprocess runs through a throwaway conftest that re-exports
      the repository's own hooks by path — `xfail`, `pytest.skip()` and a module `skipif` exit
      non-zero naming the test; a clean file exits 0.
- [x] Sabotage proof, both directions: with `pytest_runtest_logreport` exempting `wasxfail` the suite
      goes RED naming that hook; restored, and with `pytest_report_teststatus` exempting `wasxfail`,
      RED naming that hook; restored → GREEN. (The exit-status half was seen red too: before
      `pytest_sessionfinish` the e2e assertion failed with "an xfail run stayed green".)
- [x] `docs/TESTING.md` (new, linked from `README.md`) states the xfail position and the tracked-defect
      pattern with its mechanical removal; a test asserts the page keeps saying it.
- [x] `agent-wiki/2026-10-31-no-skip-guard-one-contract.md` + its `docs/changes.d/` row;
      `make check-docs` green.
- [x] `make test-unit` green with the new file inside the discovered suite (and no existing test
      relying on a skipped report). CI `linux / unit` passed 3349 tests including
      `tests/test_no_skip_guard.py`.
- [x] `make ci-unit` green, `make check-wiring`, `make check-docs`, `make check-workflows`,
      `make check-pr-hygiene` green.
- [x] `make openspec-validate NAME=no-skip-guard-one-contract` passes.
- [x] PR #1172 opened ready-for-review against `asimov-agent/llgenie:main` from
      `andyholst:fix/1110-conftest-hooks-agree` with `closes #1110`; auto-merge armed and read back.
