# worktree-base-origin-main — proposal

Issue: [#845](https://github.com/asimov-agent/llgenie/issues/845)

## Why

A kanban `worktree` task inherits the base of the **currently checked-out branch**
in `/home/asimov/repository/git/llgenie`, not `origin/main`. The primary checkout
is routinely parked on a PR branch by whichever lane last worked there, so a
worktree spawned from kanban silently starts on someone else's unmerged diff. The
base sha is recorded nowhere in the artifact, so the defect is invisible in the
PR title, the branch name and the diff stat.

Measured twice on 2026-10-28 at `main@17cdcf3`:

- lane `t_8f80762a` (#794) produced a worktree **byte-identical to PR #813's head**
  (`git rev-parse origin/pr813^{tree}`), one commit ahead of main, with all of
  #794's own work uncommitted in 10 paths — a PR opened from it would have carried
  `scripts/engine_runner.py` + `tests/test_engine_runner_failfast.py` (a duplicate
  of #813) under a `closes #794` body;
- lane #842 (`llgenie-engine-improver`) committed three commits (`e95ad1c`,
  `95ee981`, `1266c44`) **in the primary checkout itself**, with the branch never
  pushed (`git ls-remote --heads origin feat/check-engine-launchers` empty, no PR).

## What Changes

- `scripts/worktree_base.py` (new): `resolve_base()` reads only `refs/remotes/origin/main`
  (fetching `origin main` first), never the primary checkout's `HEAD`; `add --path DIR
  --branch NAME` passes that resolved base as the explicit start point of `git worktree
  add`, so a lane is cut from `origin/main` regardless of what the primary is parked on.
  (`make worktree-base` wires it.)
- `scripts/bot_preflight.py`: `base_line()` records `BASE: <sha> (== origin/main at open)`
  directly beside the existing `AGENTS: <sha> <bytes>b <lines>l` line, so the base is
  provable from the PR body without consulting the branch.
- `scripts/check_pr_base.py` (new): the foreign-commit gate. Fails when
  `git merge-base refs/remotes/origin/main HEAD` is not `origin/main` itself (the branch
  carries another PR's diff), naming the foreign commit(s); stays green for a clean
  branch one commit ahead (negative control). Wired into `ci-unit` and the CI guard job
  as `make check-pr-base`; `refs/remotes/origin/main` is refreshed before the read.
- `scripts/worktree_report.py`: each row now reports the worktree's `ahead`/`behind`
  versus the base and its uncommitted paths, so the primary checkout parked on a PR
  branch is visible before it seeds the next worktree. Mutates nothing, auto-checks-out
  nothing, prunes nothing.
- Tests: `tests/test_worktree_base.py`, `tests/test_check_pr_base.py`,
  `tests/test_bot_preflight_base_line.py`, `tests/test_worktree_report_drift.py`.
- `agent-wiki/2026-11-02-worktree-base-origin-main.md`: dated work record.

## Not covered

- `make worktree-prune` remains owner-only (#794) — out of scope for this change.
- Re-implementing #794 or #813, and recovering the #842 branch (recorded on that issue,
  work preserved as patches + bundle) — explicitly out of scope per the issue.
- A rewrite of the kanban board itself; the dispatch seam here makes the *worktree
  creation* cut from `origin/main`, which is where the defect lives.

Refs: #792 (the preflight rule that every lane starts from `origin/main`), #794/#813
(the measured instances), #845 (this change).
