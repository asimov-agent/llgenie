# llgenie checkout: remotes, worktrees, PR head

Measured on the host checkout `/home/asimov/repository/git/llgenie` (2026-10).
AGENTS.md describes `origin` as the fork; the checkout's remotes are the other way round — always run
`git remote -v` before pushing.

```
origin  https://github.com/asimov-agent/llgenie.git   # UPSTREAM (base of every PR)
fork    https://github.com/andyholst/llgenie.git      # the user's fork (head branch lives here)
```

- Agent worktrees: `git worktree add -b <type>/<kebab> ../llgenie-wt/<kebab> origin/main`, then
  work, commit and `make` gates inside that directory. Never edit the user's checkout.
- Push the branch to `fork`; open the PR with base `asimov-agent/llgenie:main`, head
  `andyholst:<branch>`:
  `gh pr create --repo asimov-agent/llgenie --base main --head andyholst:<branch> ...`
- `origin` (upstream) is only written when a dispatched workflow must run on that ref:
  `workflow_dispatch` accepts refs that exist in `asimov-agent/llgenie` only, so a live verification of a
  dispatchable workflow needs the branch pushed to `origin` as well (and then dispatched with
  `gh workflow run <wf>.yml --repo asimov-agent/llgenie --ref <branch>`).
- `git stash` is shared per repository, not per worktree: a stash popped in one worktree can land another
  worktree's work in this one. Check `git stash list` before popping, and never pop a stash you did not
  create.
- PRs are never merged by the agent (`gh pr merge` is the user's action), even when approved.
