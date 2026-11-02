# A worktree is cut from origin/main, not the primary checkout's parked branch (issue #845)

A kanban `worktree` task inherits the base of `/home/asimov/repository/git/llgenie`'s
currently checked-out branch, not `origin/main`. The canonical checkout is routinely
parked on a PR branch by whichever lane last worked there, so a worktree spawned from
the dispatch path silently starts on someone else's unmerged diff. The base sha is
recorded nowhere, so the defect is invisible in the PR title, the branch and the diff.

Measured twice on 2026-10-28 (`main@17cdcf3`):

- lane `t_8f80762a` (#794) produced a worktree **byte-identical to PR #813's head**
  (`git rev-parse 'origin/pr813^{tree}'`), one commit ahead of main, with all of #794's
  own work uncommitted in 10 paths — a PR opened from it would have carried
  `scripts/engine_runner.py` + `tests/test_engine_runner_failfast.py` (a duplicate of
  #813) under a `closes #794` body;
- #842 (`llgenie-engine-improver`) committed three commits (`e95ad1c`, `95ee981`,
  `1266c44`) in the primary checkout itself, with the branch never pushed
  (`git ls-remote --heads origin feat/check-engine-launchers` empty, no PR).

## What changed

- `scripts/worktree_base.py` (new): `resolve_base()` reads only `refs/remotes/origin/main`
  (fetching `origin main` first), never the primary checkout's `HEAD`; `add --path DIR
  --branch NAME` passes that resolved base as the explicit start point of `git worktree
  add`, so a lane is cut from `origin/main` regardless of what the primary is parked on.
  `make worktree-base` wires it.
- `scripts/bot_preflight.py`: records `BASE: <sha> (== origin/main at open)` directly
  beside the existing `AGENTS: <sha> <bytes>b <lines>l` line, so the base is provable
  from the PR body without the branch (criterion 2). `check_pr_hygiene` enforces it: a
  bot body with an `AGENTS:` line but no `BASE:` line (or a `BASE:` naming a different
  sha than AGENTS) is a `base-line` finding (criterion 2, enforced).
- `scripts/check_pr_base.py` (new): `make check-pr-base` fails a PR when
  `git merge-base refs/remotes/origin/main HEAD` is not `origin/main` itself — the branch
  carries another PR's diff (the #794 case) — naming the foreign commit; it stays green
  for a clean branch one commit ahead (negative control). Wired into `ci-unit` and the CI
  guard job; the base ref is refreshed before the read (issue #1527).
- `scripts/worktree_report.py`: each row now reports the worktree's `ahead`/`behind`
  versus the base and its uncommitted paths, so the primary checkout parked on a PR
  branch is visible before it seeds the next worktree. Mutates nothing (issue #794's
  "never auto-check-out, never prune" contract kept).

## Proof

- Criterion 1 + 5 (unit-real): `tests/test_worktree_base.py` parks the primary checkout
  on a diverged PR branch and proves the new worktree's `HEAD == origin/main`;
  `tests/test_check_pr_base.py` proves the gate fails a foreign-merge-base branch
  (naming the commit) and stays green on a clean one-ahead branch. 15 new tests pass
  across both files.
- `make check-pr-base PR_BASE=origin/main PR_HEAD=HEAD` on this very branch FAILS because
  the branch is cut at my old base `4e533896` while `origin/main` has advanced to
  `33d11fa3` — prove the gate fires on a behind-main branch too, and that a rebase onto
  fresh `origin/main` (done before push) turns it green.

## Status

Branch `agent/issue-845-worktree-base`; PR #XXXX (opened after rebase onto fresh
`origin/main`); gates via `make lane-preflight` and the PR's CI run.

Refs: #845 (this issue), #792 (every lane starts from `origin/main`), #813/#794 (the
measured instances), #1527 (live origin/main before a gate reads the base).
