# Triaging a backlog of open issues (fan-out)

Use when the ask is "go over the issues that have no PR yet and fix each". A repo with an
issue-filing bot accumulates dozens; reading them one at a time costs the whole session
before the first edit.

## 1. Build the queue programmatically, never by eye

- Open issues MINUS the ones an OPEN PR actually **closes**: read each PR's
  `closingIssuesReferences` (`gh pr list --json number,headRefName,closingIssuesReferences`).
  A body-text grep for `#N` counts refresh PRs that merely CITE a tracking issue and
  reports "has a PR" for an issue nobody is working.
- Write the queue to one JSON file in the workspace, then print each issue's body size
  so a giant one is visible before it lands in context.

## 2. Fan out READ-ONLY triage

- One subagent per ~7 issues, up to ten in parallel; each gets the repo path, the JSON
  path, its exact numbers, and: **do not trust the body; verify by running commands;
  never modify the repo.**
- Same verdict contract from every child: one JSON object per issue with `verdict`,
  `evidence`, `fix`. Verdicts: `already-fixed`, `premise-dead`, `duplicate`,
  `decision-needed`, `implement`.
- **Evidence is mandatory and checkable** — a `path:line`, a grep hit, or a command with
  its output. A prose-only verdict earns nothing: a lazy close buries a live gap and a
  lazy refine parks one.
- Point the children at the mechanisms each issue concerns (`scripts/`, the workflows,
  the tests) so they answer from the tree, not from the issue text.

## 3. Reconcile before acting

Two children can contradict each other about the SAME subject — one calling a gap
`premise-dead` (the contract now holds the key; remaining rows simply state nothing)
while another calls it `implement` (the data really is missing). Both can be true:

- re-derive the decisive claim once, yourself;
- keep ONE tracker per recurring subject, and close older filings as duplicates
  **against the surviving one** — closing them against an issue you also close leaves
  nothing to point at;
- say in the report that the verdicts disagreed rather than silently picking a side.

Recurring per-day filings of one dimension (`data-gap: <key> (N models)` on five days)
are ONE work item. Diff the bodies before treating them as independent.

## 4. Act by verdict class

| verdict | action |
|---|---|
| already-fixed | close, citing the commit / PR / test that did it |
| premise-dead | close as not-planned, naming what replaced the mechanism |
| duplicate | close against the surviving tracker |
| decision-needed | surface the named options; implement NONE — the body is asking its owner to pick |
| implement | one change, one tracked spec change, one RED-proved guard, one PR |

Never mass-implement to hit a number: one verified change plus an honest count beats ten
unreviewed branches, and the repo's own bots keep landing work while you triage.

## 5. Report counts, not impressions

State open / with-an-open-PR / without-PR and the per-verdict tallies. A backlog of
dozens is not one session's work; saying so with numbers — and naming the two or three
that landed — is the honest answer, and it lets the next session resume from a queue
instead of re-deriving it.

## Two diagnosis traps met while working such a queue

- **A fix round runs the BRANCH's `Makefile` and agent skills, not the base's.** A branch
  cut before a contract fix keeps the old prompt/skill set, so the round repeats the
  exact failure the base already fixed — and the base merge that would carry the fix is
  the one that conflicted. Check `behind_base=N` and whether the branch's recipe/skill
  copy predates the fix before re-diagnosing "the agent still detaches".
- **A wiring test that restates the shipped YAML cannot fail when the YAML is wrong.**
  `assert 'if: steps.pick.outputs.issue == ""' in step['if']` stays green while that
  very gate IS the bug, and it only reds when someone edits the file — so the fix
  deletes the guard. Assert the INVARIANT ("this step is not gated on the pick", "this
  value is never split on whitespace") and prove it RED by restoring the old file.
