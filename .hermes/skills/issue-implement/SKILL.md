---
name: issue-implement
description: Implement the issue in issue.md inside the agent container — its acceptance criteria only, every gate through the Makefile, OpenSpec change first, and pr-body.md with Issue/Fix/Benefit/Technical before you stop.
---

# issue-implement

You are the implementing agent for one issue of `asimov-agent/llgenie`, running inside the
agent container against a single writable checkout.

## Inputs

- `issue.md` at the repo root — **read it FIRST**. It carries the issue body, its whole
  comment thread (oldest first), and the acceptance criteria. The thread wins over the body
  where they disagree.
- The OpenSpec change it names, when one exists
  (`openspec/changes/<name>/proposal.md`, `specs/**/spec.md`, `tasks.md`).
- `AGENTS.md` at the repo root — the repository's durable rules, and the authority for every
  workflow question this skill does not answer.

## Output

- The implementation itself: code, tests, docs, the OpenSpec change, all inside `/repo`.
- `pr-body.md` at the repo root, with exactly four labelled parts and real content in each:
  - `Issue:` the problem, naming the issue's number as `issue.md` gives it;
  - `Fix:` the mechanism you changed and why it addresses the cause;
  - `Benefit:` what it buys and what it prevents;
  - `Technical:` the files, targets and tests you touched.
  The job builds the PR body from this file and refuses to open the PR without it.

## Rules

- **Implement exactly the acceptance criteria; do not widen the scope.** Out-of-scope work is a
  separate, linked issue — never prose in this change.
- **Run every gate through the Makefile, and fix what they report.** Never hand-run the tool a
  target wraps, and never report a gate green without its real output.
- **Never weaken or mock a test to get green.** The business logic under test is never replaced
  by a stub; a missing prerequisite is a loud failure, never a skip.
- **A test or script you add must be named by a make target** — nothing dead. Wire it into the
  target CI runs, and keep `make check-wiring` green.
- **Follow the lifecycle: issue -> OpenSpec change -> code -> PR.** Create the OpenSpec change
  (`proposal.md` + `specs/<cap>/spec.md` + `tasks.md`) before the code, tick each task the
  moment it is verified, and keep the issue, the spec and the code saying the same thing.
- **You are INSIDE the agent container.** `/repo` is the ONLY writable tree and it IS the tree
  this job commits: edit it in place, and do NOT create a git worktree. A path like
  `../llgenie-wt` resolves outside the mount and is deleted with the container.
- **Do not commit, do not push, do not merge, do not touch `main`.** The job commits and opens
  the PR from the tree you leave behind.
