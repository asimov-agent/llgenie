# agent-own-worktree — proposal

Issue: [#216](https://github.com/asimov-agent/llgenie/issues/216)

## Why

`AGENTS.md` tells every agent to check the feature branch out in the one clone.
Two agents then edit the same directory and move the user's checkout.

## What Changes

- Each agent works in its own git worktree at `../llgenie-wt/<kebab>`, cut from
  the latest `origin/main`, every time.
- The user's checkout is not switched and is not edited.
- Resuming a branch reuses that worktree, or attaches it when the directory
  is missing.
- A unit test reads `AGENTS.md` and fails if the "NO git worktrees" rule returns.

## Out of scope

- Changing how `make test-unit` mounts a worktree. That mount already exists.
