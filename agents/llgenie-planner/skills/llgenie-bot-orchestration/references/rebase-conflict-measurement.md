# Deciding whether a rebase is owed (file overlap ≠ conflict)

A merged PR whose diff touches the same FILES as an open PR is not evidence of a conflict.
Measure instead:

- `gh pr view <n> --json mergeStateStatus` — `DIRTY`/`CONFLICTING` is a real conflict;
  `UNSTABLE`/`BLOCKED` means checks, not conflict.
- `git merge-tree origin/main <head>` exit code, or the two hunks' line regions
  (`git diff <head>^...origin/main -- <file>`). Overlapping files with disjoint hunk
  regions merge cleanly; the git guard tests conflict, never filename overlap.

Rules that follow:

- **#1015:** `main` advancing under a `MERGEABLE` head is not a rebase trigger. Rebase only
  PRs that are genuinely conflicting at the current tip.
- A sweep dispatch is "measure first, rebase only if DIRTY" — never "rebase everything that
  touched a file some merge also touched".
- Never dispatch a rebase for a branch whose red is a non-conflict defect (missing commit
  trailer, newline, lint): a rebase rewrites the lane's branch and destroys its trail. Name
  those PRs explicitly as do-not-touch in the sweep brief and say whose assignment the red is.
- A lane reporting "all N MERGEABLE, no rebase owed" is a claim: confirm heads and
  `mergeStateStatus` yourself before recording the sweep clean.
- **A merge-tree verdict is valid only when the second argument is that PR's own `headRefOid`**
  (`gh pr view <n> --json headRefOid`), fetched in the same command. Watch for the tell of a
  malformed measurement: two different PRs returning the *same* tree hash, or a merge-tree
  conflict for a PR whose `mergeable` reads `MERGEABLE`. Both mean the command resolved the base
  or the wrong branch instead of the head — remeasure before writing a single word of the brief.
  Never resolve the head through `git ls-remote` on a guessed remote (remotes are per-clone);
  `gh pr view --json headRefOid` is remote-agnostic. Require the `mergeable` field and the
  merge-tree result to agree, then name the conflicting files in the dispatch.

## The definitive check: replay the rebase in a detached throwaway worktree

`git merge-tree` predicts, but the only proof that a branch *applies cleanly onto live main* is an actual
replay. Run it read-only in a detached worktree, never on the lane's ref:

```bash
WT=$(mktemp -d /tmp/rc.XXXXXX)
git worktree add --detach "$WT/w" origin/<branch>            # detached — no ref created/moved
git -C "$WT/w" rebase --onto <live-main-sha> $(git -C "$WT/w" merge-base HEAD <live-main-sha>) HEAD --no-verify
git -C "$WT/w" diff --name-only --diff-filter=U            # the exact conflicted files
git worktree remove --force "$WT/w"; rm -rf "$WT"         # planner never prunes shared worktrees; this temp one is ours
```

- An exit that prints `Could not apply <sha>` / `Resolve all conflicts manually` means a **real conflict** even
  when `mergeStateStatus` reads only `dirty` and no prior report named one. Surface it before dispatching:
  the lane's job is to *resolve* on the re-cut, and the owner's release un-gates the push but not the conflict.
- Count blocks per file (`grep -c '^<<<<<<<' <file>`) so the brief says "2 blocks in X, 1 in Y", not "conflicts".
- The `--no-verify` and detached worktree keep it strictly a measurement: no commit, no push, no cancel.
- Do this before telling anyone a rebase is "a clean cut pending release" — a clean-cut claim that hasn't been
  replayed is a guess, and a conflicted replay one commit later invalidates it.
