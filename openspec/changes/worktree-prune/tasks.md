# Tasks

- [x] 1. `openspec/changes/worktree-prune` — proposal + `specs/worktree-prune/spec.md` (G/W/T, a `- **Test:**` line per scenario) + this checklist, written before any code
- [x] 2. `scripts/worktree_prune.py` — eligibility from GitHub only (`headRefName` of a MERGED PR + `mergeCommit.oid` an ancestor of `--base`), `git worktree remove` without `--force`, `git branch -D`, a reason printed for every kept branch, `--dry` mutates nothing, any failure exits 2 naming the branch and step
- [x] 3. `tests/test_worktree_prune.py` — real git repositories (squash-merged branches, real worktrees) with `gh` stubbed on `PATH`: prune, dirty, closed/PR-less, merge-commit-off-base, main checkout, detached worktree, dry run, loud failure, Makefile/README wiring
- [x] 4. Makefile — `worktree-prune` target with a `##` help line, declared in `.PHONY:`, forwarding `$(if $(DRY),--dry,)`
- [x] 5. `README.md` — the command, the eligibility rule and why a squash merge needs the PR's merge commit
- [x] 6. `AGENTS.md` — the cleanup step names `make worktree-prune`
- [x] 7. `agent-wiki/2026-10-21-worktree-prune.md` — the work record, referencing issue #431 and its PR
- [ ] 8. Verified: `make test-unit` green with the new file, `make check-wiring`, `make check-docs`, `make lint`, `make check-pr-hygiene`, `make openspec-validate NAME=worktree-prune` all exit 0
