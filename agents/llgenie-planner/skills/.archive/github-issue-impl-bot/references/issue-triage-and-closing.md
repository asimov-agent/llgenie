# Triaging a backlog and closing issues

For "go over every open issue and fix what has no PR". The order matters: map, verify, then act.

## 1. Build the queue programmatically

Never trust a list, and never reuse yesterday's.

```bash
gh issue list --state open --limit 100 --json number,title,labels,createdAt,body > /tmp/open.json
gh pr list   --state open --limit 50  --json number,headRefName,closingIssuesReferences
```

- A PR "covers" an issue only through `closingIssuesReferences`. A body-text scan counts a
  refresh PR that merely CITES an issue and hides the absence.
- The queue is `open issues − covered`. Say those two numbers out loud before working; they are
  the whole scope claim.
- `git fetch origin` first and take every answer from `origin/<base>` (`git show
  origin/<base>:<path>`, `git grep <sym> origin/<base>`), never from the working checkout.

## 2. Verify by RUNNING, in parallel

Fan out one subagent per batch (~7 issues), each given the JSON path, the issue numbers, and
the verdict vocabulary. Each MUST return, per issue: the verdict, `evidence` (a `path:line`, a
`grep` hit, or a command it ran), and — for `implement` — a one-paragraph fix sketch. A
prose-only verdict is refused.

Verdicts: `already-fixed`, `premise-dead`, `duplicate`, `decision-needed`, `implement`.
Expect roughly a fifth of an old backlog to be already fixed, dead or duplicated; expecting
that is what stops a session from implementing stale prose.

Reconcile disagreements yourself: two subagents can classify the same DIMENSION as `implement`
and `premise-dead` (one reads the contract, the other the data). Keep ONE tracker per
dimension open and close the rest as its duplicates — a dimension re-filed per count is the
recurrence defect, not new information.

## 3. Closing is an action, and its flags are narrow

Post the evidence FIRST, with a file (a backticked body is command-substituted by the shell):

```bash
gh issue comment <n> --repo <o>/<r> --body-file /tmp/c<n>.md      # no --comment-file exists
gh issue close <n> --repo <o>/<r> --reason completed              # or "not planned", "duplicate"
gh issue close <n> --repo <o>/<r> --reason duplicate --duplicate-of <tracker>
```

- `--reason` accepts exactly `completed`, `not planned`, `duplicate`. `not_planned` is
  INVALID and fails after the comment already posted, so the issue stays open with a comment
  saying why it closed.
- `--duplicate-of <n>` is what links the pair; `--reason duplicate` alone does not.
- Cite a commit or a `path:line` that proves the fix landed. "Looks done" is not evidence and
  reads as a dismissal to the person who filed it.
- Close `already-fixed` as `completed`, `premise-dead` as `not planned` (naming what replaced
  the mechanism), and `duplicate` as `duplicate` with the tracker it points at.

## 4. Then implement, two issues per change at most

Each implementation is its own worktree, its own tracked OpenSpec change, its own RED-proved
suite, and its own PR — and each PR needs `validate` + `live-smoke` GREEN before you call it
verified. A repo whose `qa-validate` auto-merges will merge your PR when green: report that the
PR merged, never claim you merged it, and never push the base branch yourself.

Budget honestly: one issue-to-green-PR cycle is ~35–45 minutes of CI, so a 50-issue backlog is
several sessions. Report `fixed / closed-as-dead / still open` counts with the PR numbers and
the check conclusions, and say plainly that the backlog is not finished.
