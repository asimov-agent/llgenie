# Tasks — reduce the CHANGES.md merge-collision cost (issue #1103)

- [x] 1. `scripts/changes_index.py`: add a `resolve` subcommand — `git checkout <base> -- CHANGES.md`
      then `write()` then `git add CHANGES.md`, `--base` defaulting to `origin/main` (the issue's
      candidate 1: `git checkout <base> -- CHANGES.md && make changes-index`)
- [x] 2. `Makefile`: `changes-resolve` target (documented `## help`, runs `changes_index.py
      resolve`, `BASE=<ref>` optional, default `origin/main`) + declare it `.PHONY`
- [x] 3. `docs/BOTS.md`: document the new target and the "always take base + re-render" rule for
      the one contended file
- [x] 4. `tests/test_changes_index.py`: a real two-commit conflict test — two commits each add a
      fragment row and a `CHANGES.md` row, `git merge` conflicts on `CHANGES.md`, `resolve`
      recovers the render; assert no conflict markers, file == render, determinism test still passes
- [x] 5. `agent-wiki/2026-10-31-changes-resolve-helper.md` + its own
      `docs/changes.d/2026-10-31-changes-resolve-helper.md` fragment; `make changes-index`
      regenerates `CHANGES.md`
- [x] 6. Verify: `make changes-resolve BASE=<base>` reproduces the recipe's result on a scratch
      conflict; `git merge` on the test repo conflicts on `CHANGES.md` and resolves to the render
- [x] 7. Gates: `make openspec-validate NAME=changes-merges-auto-resolve`, `make check-docs
      check-wiring`, `make test-unit` for the touched files, `make loop`
