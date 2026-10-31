# changes-resolve-helper

Issue #1103 (#934/#1063 follow-up). Implemented `make changes-resolve` on
`agent/issue-1103-changes-collision` at main@d86c43bd.

Verified against spec: `scripts/changes_index.py` gains a `resolve` subcommand —
`git checkout <base> -- CHANGES.md`, then the renderer (`write`, what `make changes-index`
runs), then `git add CHANGES.md` — wired as `make changes-resolve` (BASE default `origin/main`),
declared `.PHONY`, documented in `docs/BOTS.md`. Determinism (`committed == rendered`, #1063)
kept strict: `resolve` re-renders from the merged fragments, and the existing
`test_the_real_index...` assertion is unchanged. The two dead ends stay rejected (recorded in
`design.md`): fragment-only regeneration (would let the published index silently omit a change)
and `.gitattributes merge=union` (a quiet duplicate — the exact defect #1063's gate exists to
catch).

Proof, real two-commit conflict in `tmp_path`:
`test_resolve_repairs_a_real_two_commit_changes_md_conflict` builds two branches each adding a
row and re-rendering `CHANGES.md`, `git merge` conflicts on `CHANGES.md`, `resolve` recovers the
render with no conflict markers, and the committed table equals `render(fragments)`. Wiring test
asserts the target + `.PHONY` + `docs/BOTS.md`.

PR: #TBD (this record updated on the PR number). Gates: `make openspec-validate
NAME=changes-merges-auto-resolve`, `make check-docs check-wiring test-unit`, loop gate.
