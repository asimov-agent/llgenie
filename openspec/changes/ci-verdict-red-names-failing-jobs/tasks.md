# ci-verdict-red-names-failing-jobs

## Tasks

- [x] Split the `verify()` non-green summary by cause in `scripts/ci_scope.py`
- [x] Track failing job names so a RED verdict names them (`1 FAILED (guard)`)
- [x] Add regression tests pinning the RED line, the unchanged NONE line and the
      unchanged green/exit-code shape
- [ ] local suites green (test_ci_verdict.py 55, scope/bot/publish 68)
- [ ] `make openspec-validate NAME=ci-verdict-red-names-failing-jobs` green
- [ ] `make check-docs` green (agent-wiki note + docs/changes.d + CHANGES.md in
      the same commit, #1123)
