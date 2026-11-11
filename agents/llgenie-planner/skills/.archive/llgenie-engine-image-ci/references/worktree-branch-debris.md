# Stale branches and worktrees in llgenie (post-merge debris)

llgenie's AGENTS.md mandates one worktree + one branch per agent task
(`git worktree add -b feat/<kebab> ../llgenie-wt/<kebab> origin/main`) and the
agent stops at the PR. Merging is the reviewer's action. Nothing then removes
the worktree or the local branch, so `git branch` and `git worktree list` grow
monotonically.

## Why it is not a loss of work

- **Merges are squashes.** A merged branch's tip is never an ancestor of
  `origin/main`, so `git branch --merged` does not list it, `git branch -d`
  refuses, and `git rev-list --left-right --count origin/main...<branch>` reports
  `ahead N` for work that landed long ago. Do not read `ahead` as unlanded.
- **A branch with no PR is usually a duplicate.** The agent re-cuts the branch
  after a rebase or a bot nudge, so the same change exists under a sibling name
  (`feat/x`, `feat/x-2`, `pr<N>`, `tmp/x`, `rebase/<n>`). Only one of those got
the PR. Match the commit subject against merged PR titles before calling the
branch unique.
- **Read the PR state from the forge**, never infer it from git ancestry:
  `gh pr list --repo asimov-agent/llgenie --state all --limit 1000 \
   --json number,state,headRefName,mergedAt`.

## Root cause to name when asked "what happened?"

The only cleanup that ever existed lived in the watch-loop dispatcher
(`cleanup_merged_worktrees()` in `scripts/watchloop_dispatch.py`). The dispatcher
and its host crontab were removed — only the CI engine-bump rebase remains — and
no `make` target replaced it. Check before asserting there is no cleaner:

    ls scripts/ | grep -iE 'watchloop|dispatch|clean'
    grep -nE '^[a-zA-Z0-9_.-]+:' Makefile | grep -iE 'clean|prune|worktree'

## Pruning

Use `git-maintenance`'s audit (read-only, prints the commands it would run):

    python3 ~/.hermes/skills/development/git-maintenance/scripts/branch_pr_audit.py \
        --repo /home/asimov/repository/git/llgenie --base origin/main

Delete only the two safe buckets — PR state `MERGED`, or no PR with an empty
`git diff origin/main...<branch>`:

    git worktree remove --force ../llgenie-wt/<kebab>
    git branch -D <branch>
    git worktree prune

Keep, and show the user, everything else: a CLOSED-but-unmerged PR, or a no-PR
branch whose three-dot diff is non-empty (today's `tmp/*` engine-bump
verification branches are exactly this).

The fork (`andyholst/llgenie`) keeps heads for already-merged PRs after the
upstream merge deletes its own; list them with
`git for-each-ref refs/remotes/fork` and compare each to `origin/main`, and never
push to or delete them without the user's go-ahead.

## Reporting shape the user expects

Lead with the counts (branches, worktrees, open PRs, open issues), then the
bucket table, then the one-sentence root cause with the commit/make evidence, and
close with an offer to prune the safe set. No narrative of the commands run.
