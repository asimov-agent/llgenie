# Tasks — split the 2,083-line Makefile into mk/*.mk

- [x] Teach `scripts/check_wiring.py` to resolve `include mk/*.mk` FIRST
      (recipes, prerequisites, `.PHONY`, help lines) and add the
      duplicate-target-across-includes + per-file line-budget findings.
- [x] Add unit tests: `check_wiring.py` fails on a duplicated target across
      includes; a moved target stays wired; a file over its line budget fails.
- [x] Split the Makefile by domain into `mk/{engines,gates,ci,security,bots,install}.mk`,
      top `Makefile` keeping version/`help`/`.PHONY`/`DEFAULT_GOAL` + includes,
      target names and recipes unchanged.
- [x] Move the five longest recipes' inline snippets into `scripts/<stage>.py`
      entry points with unit tests; each recipe `<= 3` lines.
- [x] Update `docs/ARCHITECTURE.md` claim if the split changes it; add
      agent-wiki note + docs/changes.d fragment + CHANGES.md row.
- [x] Verify parity: `make -qp` same sorted target list and `make help`
      byte-identical before/after; `make check-wiring`, `make test-unit` (3559/0),
      `make lint`, `make openspec-validate NAME=makefile-domain-split`,
      `make check-docs`, `make check-workflows`, `make check-pr-hygiene` all green.
      (`make ci-unit`/`make test` local completion could not be read back this
      session due to tool transport degradation; they run on the PR head's CI.)
- [x] PR body carries `## Acceptance criteria` `- [ ]` + `closes #800`.
