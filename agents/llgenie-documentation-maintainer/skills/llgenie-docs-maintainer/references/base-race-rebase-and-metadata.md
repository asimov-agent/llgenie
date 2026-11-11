# Base race: rebase, refresh metadata, re-run the gate

`check-pr-base` reddens when `origin/main` advanced past the sha your branch was cut from. The PR
is not wrong — its base is stale. Fix the base, refresh the body metadata, and let a fresh run
judge the new head. Do not argue with the red or rerun the old head.

## Procedure

1. Fetch main by explicit refspec and compare:
   `git fetch origin +refs/heads/main:refs/remotes/origin/main`
   `git merge-base --is-ancestor <your-cut-base> origin/main && echo LINEAR || echo DIVERGED`
   Linear → a plain rebase is safe. Diverged → stop and inspect; do not force through a conflict.
2. Rebase in the PR's own worktree, never in the primary checkout:
   `git rebase origin/main` and confirm only your own files differ (`git diff --name-only origin/main`).
3. Re-run the gates main's new commits can invalidate: index regeneration (`make changes-index`),
   `make lint`, `make check-docs`. A rebase that moves past new fragments/CHANGES rows leaves your
   fragment unindexed until you regenerate.
4. Regenerate the body metadata at the NEW base: `make bot-preflight`, then rewrite AGENTS:/BASE:/
   SYNC: lines from its output. A BASE: line naming the old cut sha is stale by construction.
5. Push the rewritten history with lease protection:
   `git push --force-with-lease origin HEAD:<branch>`
   The lease notation is `--force-with-lease`, never a refspec argument
   (`--force-with-lease origin/refs/heads/main` is an invalid push refspec).
   **Never put a commit SHA on the DESTINATION side of the refspec.** `git push origin HEAD:<sha>`
   (or `<branch>:<sha>`) does not move your branch — it creates a stray ref literally named `<sha>`
   under `refs/heads/`, the hook rejects it, and the PR head stays put while the output reads
   `[new branch]`. A SHA belongs only as the *lease value*, never after the colon; the destination is
   always the branch name: `git push --force-with-lease origin HEAD:<branch>`. If
   you already created the stray ref, `git push origin --delete <sha>` then re-push the branch.
6. Update the PR body to the fresh AGENTS:/BASE:/SYNC: block. A body-only edit does not re-trigger
   CI; the force-push to a new head sha does. Re-read the checks at the new head before claiming green.
7. Verify the branch actually moved and the old one is gone:
   `git ls-remote origin 'refs/heads/<branch>'` should print exactly one sha — the new head.

## Verifying the merge landed (field names bite)

- `gh pr view --json` has NO `merge_commit_sha` field; it rejects the whole query. Use `mergeCommit`
  (`--json state,mergedAt,mergeCommit`), or the API: `gh api repos/<owner>/<repo>/pulls/<n> --jq '.merge_commit_sha'`.
- Landing proof: `git merge-base --is-ancestor <merge_sha> origin/main && echo IN_MAIN`.
- Post-merge acceptance runs in a FRESH clean worktree at the merged tip; a dirty primary checkout
  gives a false red and proves nothing about the merged tree.

## Cleaning the vehicle

Remove your own worktree (`git worktree remove --force <path>`, then `git worktree prune`) and delete
local/remote branches you created. Remote branch-delete output is noisy: git may print `(none) ->
origin/prNNNN` lines mirroring server-side immutable `refs/pull/*` refs. That is not collateral damage;
confirm the real deletion with `git ls-remote origin 'refs/heads/<branch>'` returning zero refs rather
than trusting the printed arrows. The same goes for a `+ <old>...<new> <other-branch> (forced update)`
line printed *alongside* your delete: `git push origin --delete <yours>` names only your ref, so that
line is a concurrent push by another lane being mirrored, not damage you caused. Confirm that branch
still exists at its new sha (`git ls-remote origin 'refs/heads/<other-branch>'`) before reporting, and
never re-delete or reset another lane's branch to "tidy" it.
