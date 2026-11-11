# Tasks — worktree-prune-two-path

- [x] 1. `openspec/changes/worktree-prune-two-path` — proposal + `specs/worktree-prune-two-path/spec.md` (G/W/T per scenario with a `- **Test:**` line) + this checklist, written before resuming the implementation
- [x] 2. `scripts/worktree_prune.py` — two-path eligibility (PR-merged OR [no open PR AND no open issue AND head is an ancestor of the base]); the three guards conjunctive; a head ahead of the base never deleted; the base's own local branch never a candidate
- [x] 3. `issue_token()` (reads `issue-NNN` / `<NNNN>-`) and `issue_state()` (closed/absent = not-open) drive the open-issue gate; `delete_remote_branch()` deletes `origin/<branch>` after a local prune, gated on no open PR, no-op on a missing ref, records a failed push
- [x] 4. `tests/test_worktree_prune.py` — `_gh_stub` answers `issue view` from `issues.json`; new cases: ancestry-prune, open-issue keep, closed/absent-issue keep-rule, ahead-of-main keep (negative control), open-PR keep, merged-remote-deleted, live-open-PR-keeps-remote — `31 passed`
- [x] 5. Makefile — `worktree-prune` help line states the two-path eligibility and the anti-merge bound (the canonical `reclaim-tmp-worktrees` target already landed via #2141)
- [x] 6. Orchestrator tick prompt STEP 10 — the /tmp step calls `make reclaim-tmp-worktrees DRY=0`, the ancestry-gated pass, never FORCE (the #794 owner exception)
- [x] 7. Docs `agent-wiki/2026-11-09-worktree-prune-two-path-2262.md` + `docs/changes.d/` row + `make changes-index` — `make check-docs` green
- [x] 8. Verified: `make check-docs`, `make changes-index`, `make check-wiring`, `make lane-preflight` exit 0; `make reclaim-tmp-worktrees DRY=1` ran clean
