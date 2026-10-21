# worktree-prune — proposal

Issue: [#431](https://github.com/asimov-agent/llgenie/issues/431)

## Why

The checkout accumulates a worktree and a local branch for every PR the repository ever merged, and
nothing prunes them. Measured on this host on 2026-10-20: **138 local branches, 93 worktrees under
`../llgenie-wt`, 955 MB, zero open PRs**. 98 branches named the head of a MERGED PR, 2 a CLOSED
unmerged one, 37 none at all.

Three facts compound, and none of them is a mistake on its own:

1. AGENTS.md mandates a fresh `git worktree add -b feat/<kebab>` per agent, and the agent **stops at
   the PR** — the merge is the reviewer's action, so no agent step ever sees a merge happen.
2. The only sweep that ever existed, `cleanup_merged_worktrees()` in the watch-loop dispatcher, was
   deleted with the dispatcher in `99ce5b9` (#211). `make help` carries no worktree/prune target.
3. Squash merges defeat every usual signal: a squashed branch's tip is never an ancestor of `main`,
   so `git branch --merged` and `git merge-base --is-ancestor` report it unmerged forever and
   `git branch -d` refuses. Only the **PR's merge commit** proves the work landed, and nothing reads it.

The result is a branch list that hides both facts it should show: which work merged, and which work
is still outstanding. A resumed agent can also attach to a dead worktree.

## What Changes

- **`scripts/worktree_prune.py`** (new, stdlib only). Eligibility comes from GitHub, never from a
  name pattern or an ancestry guess: a local branch is prunable **only** when it is the
  `headRefName` of a MERGED PR **and** that PR's `mergeCommit.oid` is an ancestor of the base
  (`origin/main` by default, `--base` overrides). For each such branch it runs `git worktree remove
  <path>` (never `--force`, so a dirty worktree stops it) and then `git branch -D`.
- **It refuses, by construction**: the repository's main checkout, a detached-HEAD worktree, a dirty
  worktree, a branch naming an OPEN or CLOSED PR, a branch naming no PR at all, and a branch whose
  merge commit is not on the base. Each refusal prints its reason, so a kept branch is a decision
  with evidence rather than a silent omission.
- **`make worktree-prune`** drives it (`DRY=1` prints the plan and mutates nothing; `BASE=` and
  `REPO=` override the base ref and the slug), declared in `.PHONY:` and carrying a `make help` line.
- **`tests/test_worktree_prune.py`** exercises the real `git` operations against a real temporary
  repository whose merged branches are squash-merged (the state that defeats ancestry), with `gh`
  stubbed on `PATH` — the repository's documented allowance for an external CLI. It pins every
  refusal direction and proves `DRY=1` mutates nothing.
- **`README.md`** documents the command and the eligibility rule; **`AGENTS.md`** names the target
  in its cleanup step; **`agent-wiki/2026-10-21-worktree-prune.md`** records the change against
  issue #431.

## Not covered

- The fork's stale heads (`andyholst/llgenie` keeps a head for every merged PR) — issue #432.
- Containerized `make` stages leaving root-owned `__pycache__`/`.pytest_cache` inside a worktree,
  which makes `git worktree remove` fail after the branch is gone — issue #433.
- Branches with no PR at all (37 measured) are left alone on purpose: deciding which of them is
  abandoned work is a human judgement, not a rule this target may invent.
- The `REPO` collision behind `issue-cleaner-scan`/`queued-alarm` (`REPO` is the checkout path, so
  their documented default reaches `gh` as a path and fails) — issue #434. This target uses `SLUG=`
  for that reason and says so, but does not repair the other two recipes here.
