# Tasks

- [x] `scripts/check_architecture_census.py`: `git_unreadable()` probe — a `git rev-parse --git-dir`
      run in `REPO_ROOT` whose failure (non-zero return / raised invocation / stderr naming a
      git-environment failure) marks an unreadable checkout.
- [x] `check()` calls the probe first and, on an unreadable checkout, emits an `UNREADABLE` finding
      naming the checkout/git and exits 2; exit codes documented in the module docstring.
- [x] The dangling-pointer message keeps `not a real commit` but drops "(dangling from an amend?)";
      a genuinely bad pointer in a readable repo still exits 1 with the old message.
- [x] `tests/test_architecture_census.py`: new test asserting an unreadable checkout → `UNREADABLE`
      naming git (not the doc) and exit 2; existing tests for the bad-pointer (exit 1) and clean
      clone (exit 0) cases kept and passing.
- [x] Sabotage proof: temporarily disable the `git_unreadable()` probe (make `check()` judge the
      pointer directly) → the unreadable-checkout test goes RED naming the missing `UNREADABLE` /
      exit 2; restore → GREEN.
- [x] `agent-wiki/2026-10-31-census-git-failure-diagnostic.md` + its `docs/changes.d/` row;
      `make check-docs` green.
- [x] `make test-unit` green with the new/edited census tests in the discovered suite.
- [x] `make check-architecture-census`, `make check-docs`, `make check-wiring`, `make ci-unit` green.
- [x] `make openspec-validate NAME=census-git-failure-diagnostic` passes.
- [ ] PR opened ready-for-review against `asimov-agent/llgenie:main` from
      `andyholst:fix/1141-census-git-failure-diagnostic` with `closes #1141`.
