# Sweep for an existing vehicle before you branch on a dispatched issue

A dispatch naming an issue to implement says the issue is worth doing. It does NOT say nothing is already doing it. The dispatcher's message is a claim about priority, never a census of the board.

## The sweep, before the first edit

```bash
gh pr list --repo <canonical> --state all --search "<issue-number>" --json number,title,state,headRefName,createdAt
```

Run it before `git worktree add` and before `gh pr create`. An OPEN PR that closes the issue IS the vehicle.

## What a duplicate costs

Do not open a second PR for a one-issue contract — not to "improve" it, not because yours is better, not because its head is stale. Two branches, two sets of red CI, and a reviewer who cannot tell which green means done. A duplicate is worse than doing nothing.

Contribute by *reporting*: a comment on the existing PR carrying your measurement, the file:line, and a proposed patch. Never push to its branch. Never race it with your own.

## Two corollaries

- **A stale head is not a licence to fork.** Check the issue's own acceptance criteria: when they cite a reviewer verdict at a *specific head*, that head is the live vehicle and it will not be yours. Its staleness is the vehicle's current state, not an invitation.
- **Anything derived from a duplicate is contaminated.** A tree you built, a live profile you propagated into, a gate you wired — all reasoned from a shape that is not the one merging. If you find the duplicate after mutating shared state: restore that state from a pre-change snapshot, verify it byte-for-byte, and say so plainly in the report. Never leave the environment reflecting a branch that will never land.

## Signal that you are already in this trap

You are probably duplicating when you notice yourself explaining why the existing PR "does not really" cover the issue. That reasoning is the tell. The honest move is to measure the existing vehicle's actual state, post what is genuinely missing there, and stand down.
