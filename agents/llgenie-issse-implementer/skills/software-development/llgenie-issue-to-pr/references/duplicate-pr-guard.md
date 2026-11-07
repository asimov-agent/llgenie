# Duplicate-PR guard (#1644, session 2026-11-05)

When the terminal/output channel degrades mid-`pr create`, you can double-open the SAME
branch as two PRs: one with fork-head (`owner:ref`) and one with origin-head (`ref`), each
carrying the same correct body. The 2nd `gh pr create` for the *first* head form answers
"already exists" while the *second* head form silently creates a second PR — both OPEN.

## Do

- One-issue-one-PR. Keep the earlier PR (compare `createdAt` / `headRepository` /
  `baseRefOid` via `gh pr view N --json number,createdAt,state,headRepository,baseRefOid`).
- Close the later duplicate with a comment naming it a duplicate of the kept PR
  (`gh issue comment N --body-file ...` then `gh pr close N --comment ...`).
- Verify read-back: `gh pr list --head <ref>` shows exactly ONE OPEN PR, the duplicate
  CLOSED (`gh pr view N --json state,closed`). Do NOT guess a PR number.

## Why

Two open PRs on one branch break the fleet's one-vehicle rule and the merge queue sees a
board wit a dead row. The close comment is the audit trail a reader can find.

The skill (SKILL.md) has a 100k size cap; this reference is the home for the rule.
