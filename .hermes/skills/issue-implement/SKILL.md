---
name: issue-implement
description: Use when an llgenie issue-bot run must implement ONE issue from issue.md in the agent container, write its PR body, and leave the tree for the job to commit.
version: 1.0.0
author: Asimov Agent
license: CC-BY-4.0
metadata:
  hermes:
    tags: [llgenie, bots, issue-bot, implementation]
---

# Issue implementation

The biggest leg: it turns one issue into a reviewable change. The job commits and opens the PR from
what you leave behind, so the tree and `pr-body.md` are the deliverable.

## Inputs

- `issue.md` at the repo root: the issue, its whole comment thread, and the verdict block. Its
  **acceptance criteria are the scope** — implement exactly those, no widening.
- The OpenSpec change it links, when there is one.
- `AGENTS.md`: the repository's rules. They are the authority; this skill never overrides them.

## Output

- **The change, in `/repo`, uncommitted.** You are INSIDE the agent container: `/repo` is the only
  writable tree and it IS the tree the job commits. Edit it in place.
- **`pr-body.md` at the repo root**, with exactly four labelled parts, real content in each:
  `Issue:` (the problem, naming the issue's number as `issue.md` gives it), `Fix:` (the mechanism
  you changed and why it addresses the cause), `Benefit:` (what it buys and what it prevents),
  `Technical:` (the files, targets and tests you touched). The job refuses to open the PR without
  this file.

## Rules

- **Never create a git worktree.** AGENTS.md's worktree rule is for a host agent; here `../llgenie-wt`
  resolves outside the mount and is destroyed with the container, taking your work with it.
- **Every gate runs through the Makefile** (`make test-unit`, `make lint`, `make check-wiring`,
  `make check-docs`, `make openspec-validate NAME=<change>` …). Fix what they report; CI runs the
  same commands.
- **Never weaken, mock or skip a test to get green.** A red gate you cannot fix honestly is a
  result: leave the tree as it was and say so in `pr-body.md`.
- **Nothing dead.** A test or script you add must be named by a make target CI runs, or
  `make check-wiring` fails — that is by design, not an obstacle.
- **One OpenSpec change for the behaviour**, with `proposal.md`, `specs/<cap>/spec.md` (Given/When/
  Then, a `- **Test:**` line per scenario) and `tasks.md` ticked as you verify each step.
- **Documentation is part of the change**: README for anything user-facing, an `agent-wiki/` entry
  naming the issue and the PR.
- **Do not commit, do not push, do not merge, do not touch `main`.** The job does that.
