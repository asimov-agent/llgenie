# ci-verdict-final-red-names-verdict

## Tasks

- [x] Make `scripts/ci_verdict.py::main`'s final `FAILED:` stderr line verdict-aware:
      `red` → "is RED" + failed jobs; `none` → keep the #1111 wording; `green`+unjudged →
      name the unjudged-red cause
- [x] Add a regression test pinning the RED final line and that the NONE line is unchanged
- [x] local suites green (test_ci_verdict.py + the make gates the change touches)
- [x] `make openspec-validate NAME=ci-verdict-final-red-names-verdict` green
- [x] sabotage: plant the old "has no verdict" line, show the specific case RED (quote the
      run), restore, show GREEN
