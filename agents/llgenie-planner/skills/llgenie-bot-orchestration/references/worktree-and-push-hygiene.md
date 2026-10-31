# Worktree and push hygiene

Siblings: `references/ci-failure-diagnosis.md` (red vs cancelled vs queued, reading logs, timeouts, reruns) · `references/pr-approval-and-merge.md` (approver identity, auto-merge, fork vs same-repo heads).

## `git reset --hard` in another lane's worktree is destruction, not tidying

A rebase sweep never needs `reset --hard`. Before any branch move:

```
git status --porcelain           # dirty paths -> report, do not move
git log --oneline <remote>..HEAD # unpushed commits -> report, do not move
```

Anything listed is work that exists on no remote and is invisible to every check. A `reset --hard` to the remote head destroys it silently; a local-only commit survives only if someone happens to have tagged it. The tree is read-only the moment `git log <remote>..HEAD` is non-empty.

## "Ahead N commits" is not evidence of unique work

A worktree 10 commits ahead of its remote is almost always an **older base**, not unpublished work — a tree diff between an older and a newer base is non-empty by construction. The test that decides, per file:

1. diff the worktree against `main`, against the target PR's remote, and against the branch's own remote;
2. compare **blob equality** per path, not line counts;
3. a file matching one of the three sources is older; a file matching none is worth reporting.

Only after that proof may a worktree be re-pointed — and re-pointing never force-pushes a branch.

## One worktree per PR, and check the branch before the first edit

`git rev-parse --abbrev-ref HEAD` before writing a single line. A worktree reused for a second PR is how a one-file change becomes an unrelated diff that a reviewer has to reverse-engineer.

## A push exits 0 yet the ref is not on the remote — verify with `ls-remote`

`git push -q -u origin $BR` can report success and still leave the branch off the remote. Two mechanisms
produce a false green, and both are silent:

- a **non-exported shell variable** set in an *earlier* terminal call is **gone** in the next call, so `$BR`
expands to empty and the refspec is garbled or defaults to the wrong thing — `-q` swallows the complaint and
  the exit code is not the fact;
- `-u` on a first push of a branch with no upstream resolves the tracking ref to whatever it can (often
  `origin/main`), so `git rev-parse --symbolic-full-name @{u}` returning a ref is **not** proof the branch landed.

The only fact is the remote's ref. After every push, before believing it:

```
git ls-remote origin refs/heads/<branch>      # empty => it did NOT land
```

If empty, re-push with the literal ref, never a variable whose scope you did not just set:
`git push -v origin HEAD:refs/heads/<branch>`. Carrying a shell variable across `terminal` calls is a coin flip —
re-declare it in the same command or inline the value.

## Never push while a run at the head is in progress

`concurrency: <workflow>-${{ github.ref }}` with `cancel-in-progress: true` means a push destroys the verdict the previous head was earning. Trigger a push on *the run concluding*, never on the licence arriving. A run that is **queued and has never acquired a runner** owes no verdict, so superseding it is legitimate where superseding a running one is not.

An amended or re-cut head needs `--force-with-lease=<ref>:<value actually on the remote> --force-if-includes` after a fresh `git fetch` — the lease value is the remote's, never the value being pushed.

## There are two clones and two `main`s

A host can carry more than one clone of the same repo, naming the canonical remote differently:

```
<clone A>   origin   = <upstream org>/<repo>
<clone B>   upstream = <upstream org>/<repo>
```

Worktrees inherit whichever clone created them, so `git fetch origin main` validates a *different repository* in one tree and the right one in the other. Always: `cat .git | head -1` -> `git remote -v` -> `git ls-remote <remote> main`, then fetch/push to whichever URL is the upstream. The fork's `main` is a different commit from upstream's: fetch a cross-repo head from its own remote, rebase onto `origin/main` (the upstream sha), and push back to that PR's own head remote.

## A PR that carries another PR's file must land after it

When a branch includes another open PR's commits (stacked branches, files added by both), merging the carrier first silently drops the base gate the other PR was extending. Order the merges: base PR, then the carrier, then the dependents.

## Arm auto-merge at PR creation

Immediately after `gh pr create`: `gh pr merge <n> --squash --auto`, then verify `gh pr view <n> --json autoMergeRequest`. Do not arm a draft, a `do-not-merge` PR, or one based on a non-`main` branch — report those as deliberately unarmed with the reason. Arming is not approving: `auto-merge.yml` still performs the review with a second identity, and a red PR is never merged because `REQUIRED_MERGE_STATE = "CLEAN"`.

When the owner has decided a state change applies repo-wide (arm auto-merge, add a label, retarget a base), **apply it to every eligible PR in one pass and report the exceptions** rather than doing one and waiting to be asked again. Loop with the eligibility checks inline, print `armed=<n>` and the skipped list with each skip's reason, and only then report. The owner experiences one-at-a-time execution as the work not being done.

## Never prune a worktree

`make worktree-prune`, `git worktree prune`, `git worktree remove` are forbidden unless the owner says so. The prune's "already merged" test reads the branch ref only, so it cannot see uncommitted work — and the trees it would destroy are exactly the merged-head, no-open-PR, dirty ones. Measure with `git worktree list --porcelain` and report; a report target that cannot delete is the supported operation.
