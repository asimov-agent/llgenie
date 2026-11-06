# Tasks

- [x] `scripts/ci_verdict.py::main()` drops the job row named `CHECK_NAME` (`ci-verdict`) from the observed set before `ci_scope.verify()` — the verdict does not judge its own posted check-run (measured run `42275871131` @ `cf88d285`, #1882).
- [x] Regression test `tests/test_ci_verdict.py::test_the_verdict_does_not_judge_its_own_posted_check_run`: a full-matrix decision + 10 green real jobs + an 11th `ci-verdict` failure row judges green (exit 0, `verdict=green`, no `ci-verdict FAILED`).
- [x] Existing behavior preserved: `tests/test_ci_verdict.py` 33 tests pass (real-failure red cases unchanged); the fix is verified against the real reproduction data (run `42275871131` jobs + decision → `verdict=green`).
- [x] Docs trio: `docs/changes.d/2026-11-07-ci-verdict-does-not-judge-itself-1882.md` (one table row) + `agent-wiki/2026-11-07-ci-verdict-does-not-judge-itself-1882.md` narrative + regenerated `CHANGES.md`; `check_docs.py check` green.
- [x] PR body carries `AGENTS:`/`BASE:` (#792) and `closes #1882`; normal review flow (#1644 acceptance write-back, owner merges). No merge/arm (#1088).