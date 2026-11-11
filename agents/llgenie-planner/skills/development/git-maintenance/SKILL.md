---
name: git-maintenance
description: Maintain and repair large, broken, or partial-clone git repositories — gc, packfile, ownership, fetch failures.
triggers:
- "git commands timing out or hanging on large repos"
- "repo packfile is bloated (>1GB)"
- "need to tune git for large objects or slow networks"
- "git gc fails or is slow"
- "permission errors inside .git/objects"
- "need to recover disk space from a git repo"
- "dozens of stale local branches / worktrees left after merged PRs"
- "a branch is behind main but its PR already merged — is the work lost?"
- "git fetch fails with a pack-objects BUG on a partial clone"
- "hermes update fails to fetch: pack-objects died"
---

# Git Maintenance

Performance tuning, gc, and repair for large or broken git repositories.

## Diagnosing Slowness

Check repo size and packfile health:
    du -sh .git/
    git count-objects -vH

Check for root-owned objects blocking operations:
    find .git -not -user $USER -ls

Common symptoms:
- `git status` takes >5 seconds on small working trees
- Packfile >1GB with many loose objects
- `git gc` fails with "Permission denied" on specific objects
- Push/pull times out on slow connections

## Config Tuning for Large Repos

When git commands time out on large repos, tune the local `.git/config`:

    git config http.postBuffer 524288000
    git config http.lowSpeedLimit 1000
    git config http.lowSpeedTime 60
    git config core.bigFileThreshold 512m
    git config core.packedGitLimit 512m
    git config core.packedGitWindowSize 512m
    git config pack.windowMemory 512m
    git config pack.threads 2

## Aggressive GC

Standard `git gc` is conservative. For badly bloated repos:

    git gc --prune=now --aggressive

If gc fails with permission errors on specific objects, fix ownership first:

    find .git -not -user $USER -ls
    sudo chown -R $(whoami):$(whoami) .git/objects/<prefix>

Then re-run gc.

## Partial clones that fail to fetch

A partial clone (`--filter=tree:0` / `blob:none`, promisor) can abort every `git fetch` with
`BUG: pack-objects.c ... should_include_obj should only be called on existing objects` +
`could not finish pack-objects to repack local links` while `git status`/`log` still work.
Try `git -c fetch.writeCommitGraph=false fetch` to unblock; the robust fix is converting to
a full clone (unset the promisor/filter config, re-fetch every object). Full recipe:
`references/partial-clone-repair.md`.

## Stale worktrees and branches (post-merge debris)

A repo driven by one-worktree-per-task agents accumulates dead branches and
worktree dirs faster than anyone prunes them. Never delete, and never report
"this work was lost", from `git` alone — a squash merge rewrites the branch into
one new commit, so the branch's tip is **not** an ancestor of the base branch:
`git branch --merged` misses it, `git branch -d` refuses it, and
`rev-list --left-right --count main...branch` shows a healthy `ahead N` for work
that landed weeks ago. The forge's PR state is the only truth.

Audit first (read-only, prints the prune commands it would run):

    python3 scripts/branch_pr_audit.py --repo . --base origin/main

It joins every local branch to `gh pr list --state all --json headRefName,state`
and buckets each one:

| verdict | meaning | action |
|---|---|---|
| pr-merged | the squash commit is on base | safe: `git worktree remove` + `git branch -D` |
| pr-open | in flight | keep |
| pr-closed-unmerged | rejected or superseded | review before deleting |
| no-pr, content on base | `git diff base...branch` is empty | safe: same as pr-merged |
| no-pr, N files unique | unreviewed work | keep and look at it |

A branch with **no PR** is usually a duplicate of a sibling branch that did get
one (a second cut of the same task after a rebase, `pr<N>`/`<name>-2`/`tmp/*`
scratch), not abandoned work. Confirm by matching its commit subject to merged
PR titles before calling it unique.

**`pr-merged` from `gh` is not yet permission to delete — verify the merge landed.**
Fetch `mergeCommit.oid` with the PR state and require it on the base branch; a
PR can be MERGED against a stale base, or the local base ref can be behind.

    gh pr list --repo <slug> --state merged --limit 500 \
        --json number,headRefName,mergeCommit
    git merge-base --is-ancestor <mergeCommit.oid> origin/main && echo landed

Delete only on exit 0, and count first: "N verified, 0 unverified".

Prune in this order, and only the verified `pr-merged` / `content on base` buckets:

    python3 scripts/branch_pr_audit.py --repo . --base origin/main            # audit only
    python3 scripts/branch_pr_audit.py --repo . --base origin/main --apply    # prune the safe buckets

The script maps branch -> worktree, checks each worktree for uncommitted
changes, removes the clean ones, deletes the branches, prunes admin entries,
and prints what it skipped. By hand the same order is:

    git worktree list --porcelain          # map branch -> dir
    git -C <dir> status --porcelain        # ANY output = skip, report it
    git worktree remove <dir>              # no --force; it must refuse dirt
    git branch -D <branch>
    git worktree prune                     # drop admin entries whose dir is gone

`git branch -D` refuses a branch checked out in *any* worktree — including one
`git worktree list` displays as `(detached HEAD)` but whose gitdir still holds
the branch ref. Remove that worktree first, then delete the branch.

**Root-owned caches block the removal.** Tooling that runs tests inside a
container as root (`docker`/`nerdctl` with the worktree mounted) leaves
`__pycache__`/`.pytest_cache` owned by root inside the worktree, so
`git worktree remove` fails with `Permission denied` and leaves an unregistered
directory behind. Deleting them as the user cannot work (write access to the
directory comes from its owner); `sudo` in an agent shell may have no
passwordless path. Count them, then delete from inside a root container with
only the worktree root mounted:

    find <wt-root> -not -user "$USER" | wc -l
    docker run --rm -v "<wt-root>":/wt -w /wt <test-image> \
        sh -c 'for d in <dir1> <dir2>; do rm -rf -- "$d"; done'
    git worktree prune

Also check the fork's remote heads after `--remote`-based cleanup: a merged PR's
head is often still on the fork even though the merge deleted it upstream.
Report the before/after numbers (branches, worktrees, `du -sh <wt-root>`) —
"pruned" without counts is not evidence.

## Verification

    git count-objects -vH    # Should show: count 0, garbage 0, single pack
    du -sh .git/             # Compare before/after
    time git status          # Should be instant

## Pitfalls

- `--aggressive` gc can take 10-30 minutes on multi-GB repos — run in background
- `pack.windowMemory` over 512m on memory-constrained machines can OOM
- `http.postBuffer` must be set on both client and remote for pushes to work
- Root-owned objects usually mean a prior `sudo git <cmd>` was run — fix with `sudo chown`
- Squash-merged branches never satisfy `--merged` or `-d`; classify by PR state, and force-delete
  only branches whose PR is MERGED or whose three-dot diff against base is empty
- A worktree whose branch's PR merged can still hold uncommitted work — read
  `git -C <dir> status --porcelain` first and report dirty ones instead of
  force-removing them
- A `Permission denied` on `git worktree remove` means something inside the
  worktree is not yours (container-run tests writing caches as root), not that
  git is wrong — clear it as root in a container, then `git worktree prune`
- When a repo previously had an auto-cleanup step (a dispatcher, a bot), grep for it before
  claiming nothing cleans up — its removal is usually the root cause of a debris pileup

## Reference Data

For a full tuning reference for repos >5GB and common timeout fixes, see `references/large-repo-checklist.md`.
