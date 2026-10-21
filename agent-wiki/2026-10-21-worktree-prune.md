# `make worktree-prune` — remove the worktrees and branches whose PR already merged

Issue #431. OpenSpec change: `worktree-prune`. PR: see the branch `feat/worktree-prune`
(referenced in the issue's timeline and in the PR body with `closes #431`).

Side issues this change deliberately did NOT absorb: #432 (the fork's stale heads),
#433 (containerized stages leaving root-owned files in a worktree) and #434 (`issue-cleaner-scan` /
`queued-alarm` failing on their documented invocation, because `REPO` is the checkout path).

## What was wrong

Measured on this host, 2026-10-20, before the prune: **138 local branches, 93 worktrees under
`../llgenie-wt`, 955 MB, zero open PRs**. 98 branches named the head of a MERGED PR, 2 a CLOSED
unmerged one, 37 no PR at all.

Three facts compounded:

1. AGENTS.md mandates a worktree + branch per agent and the agent **stops at the PR**; the merge is
   the reviewer's action, so no agent step sees the merge.
2. The only sweep that existed — `cleanup_merged_worktrees()` in the watch-loop dispatcher — went
   with the dispatcher in `99ce5b9` (#211). No target replaced it.
3. **Squash merges defeat ancestry**: a squashed branch tip is never an ancestor of `main`, so
   `git branch --merged` reports landed work as unmerged forever and `git branch -d` refuses it.

## What changed

- **`scripts/worktree_prune.py`** — eligibility from the PR only: a branch is prunable when it is a
  MERGED PR's `headRefName` **and** that PR's `mergeCommit.oid` is an ancestor of `--base`
  (`origin/main`). Then `git worktree remove <path>` (no `--force`) and `git branch -D`. Kept with a
  printed reason: OPEN/CLOSED PR, no PR, merge commit off the base, dirty worktree, detached
  worktree, the main checkout. `--dry` mutates nothing; a failed lookup or git step exits 2 and
  leaves that branch in place.
- **`make worktree-prune`** (`DRY=1`, `BASE=`, `REPO=`), in `.PHONY:`, with a `make help` line and a
  README entry.
- **`tests/test_worktree_prune.py`** — 9 tests on real repositories that really squash-merge, with
  `gh` stubbed on `PATH`: prune, dirty, CLOSED/PR-less, merge-commit-off-base, main checkout,
  detached worktree, dry run, failing lookup, and the Makefile/README wiring.

## Verified

- `tests/test_worktree_prune.py` — 9 passed in `llgenie/test:latest` (run as the invoking uid).
- The live dry run against the real checkout, after the hand prune of the same day (92 merged
  branches and 69 worktrees removed, `955 MB → 184 MB`): every remaining branch was kept with its
  reason — the 36 PR-less duplicates, the 2 CLOSED-PR branches (`ci/bot-schedule-gaps` #281,
  `fix/workflow-file-valid` #334) — and nothing was removed.
- The gate set for this change: `make check-wiring`, `make check-docs`, `make lint`,
  `make check-pr-hygiene`, `make openspec-validate NAME=worktree-prune`, `make test-unit`.
