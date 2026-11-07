# Fork-PR push convention

Sibling PRs (#1681/#1680/#1655) are all **fork PRs**: head repo = `andyholst/llgenie`, branch pushed to the `fork` remote, PR head_ref `andyholst:<branch>`. A first push to `origin` (`asimov-agent/llgenie`) makes the planner's fork-ref read 404 and reads as "stalled" — the board/chaser and any reviewer key off the fork ref.

- Push the branch to `fork`, not `origin` (the `fork` remote exists in every worktree: `git push fork <branch>`).
- If you accidentally pushed only to origin: push the same commit to `fork` and keep the PR as the single vehicle — do NOT close + reopen to re-source, that is a second vehicle (#824/#1015).
- After pushing to the fork, verify: `git ls-remote fork <branch>` must show your head sha.
- A green PR whose head repo is `asimov-agent/llgenie` instead of the fork is a board-visibility divergence, not a merge blocker; state it plainly to the planner rather than silently re-sourcing.

## Open the PR from the fork, then read the fields back

`gh pr create` from inside the worktree targets the repo its remotes point at; be explicit so the
base is the canonical repo and the head is the fork:

```
gh pr create --repo asimov-agent/llgenie --base main \
  --head andyholst:<branch> --title '<type>(<scope>): … (closes #<n>)' --body-file <file>
```

**A bare `--head <branch>` (no `owner:` prefix) against a fork-sourced branch FAILS** with
`GraphQL: Head sha can't be blank, Base sha can't be blank, No commits between main and <branch>` —
the upstream repo has no such branch name, so it resolves no head. The branch IS pushed and fine;
the fix is the `andyholst:<branch>` owner prefix, not re-pushing or closing/reopening. Treat that
error as "wrong head form", retry once with the prefix.

A body file carries the literal `make bot-preflight` `AGENTS:`/`BASE:` lines and `closes #<n>`.
Then read the fields back — the create exit code is not the fact:

```
gh api repos/asimov-agent/llgenie/pulls/<n> \
  --jq '{state,is_draft,mergeable,mergeable_state,base:.base.ref,head:.head.repo.full_name}'
```

Expect `base=main`, `head=andyholst/llgenie`, `mergeable=true`, `state=open`. `is_draft` must not be
`true` (flip with `gh pr ready`). `mergeable_state=blocked` on a fresh PR is NORMAL — required
checks still computing — not a red; re-read it only after the matrix concludes. Finally run
`make check-pr-authors` and confirm `closes #<n>` and both literal preflight lines are in `.body`.

## PR head goes STUCK at the old sha after a fork force-push (rebase)

After you `git push --force-with-lease fork <branch>` a rebased head, GitHub's PR-head oracle can
stay **pinned at the OLD sha for 10+ minutes** — `gh pr view <n> --json headRefOid`,
`repos/…/git/ref/pull/<n>/head` and the checks all keep reporting the pre-rebase sha, and the PR
timeline shows **no `synchronize` event** — even though `git ls-remote fork <branch>`, the fork
branches API and the local `rev-parse` all agree the branch tip is the NEW sha. This is a
cross-fork PR-ref reconciliation lag, **not** a conflict and **not** a failed push.

- **Re-pushing the same sha is a no-op and does NOT fix it** (the ref is already there).
- **Do not revert to the stuck sha** — force-pushing back to the old sha re-creates the
  unreconciled state and can leave the PR head pointing at a sha no longer on the fork.
- **Fix: push a NEW sha** — `git commit --allow-empty -m 'ci: re-sync fork pr head'` then push.
  A brand-new commit sha forces GitHub to reconcile the PR head to it. Verify with
  `gh pr view <n> --json headRefOid` (or a fresh check run) before trusting it. The empty commit
  is benign and is dropped by the squash merge, so it never reaches main.

Only reach for this after confirming the branch tip genuinely moved and the fork ref is the new sha
(`git ls-remote fork <branch>`); a stale local `fork/…` tracking ref or a real force-push rejection
is a different problem.
