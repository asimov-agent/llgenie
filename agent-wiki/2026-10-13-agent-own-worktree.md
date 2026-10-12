# each agent, own worktree

Issue #216. `AGENTS.md` no longer says "NO git worktrees". Every agent cuts
`../llgenie-wt/<kebab>` from `origin/main` and leaves the user's checkout alone.
