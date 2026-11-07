# Tasks - docs-maintainer-2019-skill-fold

- [x] 1. Fold the 10 drifted files (SKILL.md + 6 live-longer refs + 4 live-only refs) live→tree verbatim, `cmp`-verified.
- [x] 2. Regenerate CHANGES.md from fragments (make changes-index) — no hand-edit of the index.
- [x] 3. change-note trio present: `agent-wiki/2026-11-07-docs-maintainer-2019-skill-fold.md`, `docs/changes.d/2026-11-07-docs-maintainer-2019-skill-fold.md`, `CHANGES.md` row.
- [x] 4. `make lane-preflight` green at the PR head.
- [ ] 5. Final: `make openspec-validate NAME=docs-maintainer-2019-skill-fold` exits 0 and all docs-class gates (`lint`, `check-docs`, `check-wiring`, `check-pr-hygiene`, `check-pr-authors`, `check-issue-bodies`) are green at the PR head.
