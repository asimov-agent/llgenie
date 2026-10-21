# `make worktree-prune` — remove the worktrees and branches whose PR already merged

Issue #431. OpenSpec change: `worktree-prune`. PR: [#436](https://github.com/asimov-agent/llgenie/pull/436).

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

## Review fix (PR #436)

Rebased onto `origin/main` `cbb1ff4` (#439) and hardened one real edge the first cut got wrong: when
the prune runs **from inside** a merged branch's own worktree, that worktree was a candidate and
`git worktree remove` failed with `fatal: validation failed, cannot remove working tree` — an exit-2
failure for a run that could not do what it announced. The running worktree is now never a candidate
and is reported (`is the worktree this run is executing in`), with a spec scenario and
`tests/test_worktree_prune.py::test_the_worktree_the_run_is_in_is_never_removed`. The file is now 11
tests.

CI on the first push was red only on `macos / top-tier`: a live-Hub `TimeoutError: The read operation
timed out` in `test_top_tier_acceptance.py` — the open #399 (the dry-run acceptance test blocks on Hub
latency), unrelated to this change. `linux|macos / openspec` were red earlier for one commit because
task 8 was still unticked at that commit (`openspec-tasks-check`), fixed in `7ac25fc`.

## Verified

- `tests/test_worktree_prune.py` — 11 passed in `llgenie/test:latest` (run as the invoking uid).
- The live dry run against the real checkout, after the hand prune of the same day (92 merged
  branches and 69 worktrees removed, `955 MB → 184 MB`): every remaining branch was kept with its
  reason — the 36 PR-less duplicates, the 2 CLOSED-PR branches (`ci/bot-schedule-gaps` #281,
  `fix/workflow-file-valid` #334) — and nothing was removed.
- The gate set for this change, all exit 0, re-run on the rebased branch (`cbb1ff4`): `make test-unit`
  (**4922 passed, 3 deselected, 740 s**),
  `make check-wiring`, `make check-docs`, `make lint`, `make check-pr-hygiene`, `make check-pr-authors`,
  `make openspec-validate NAME=worktree-prune`.
- `make test-unit` was red once before that, on `test_readme_links_answer_and_a_broken_copy_is_caught`:
  15 Hugging Face links answering HTTP 429. The test passes alone in 15 s, it touches no link, registry
  data or downloader, and the flake is filed as **#435** (same class as #339/#180/#256).
