# Verifying fleet dispatches before acting

The delivery layer between lanes (bot DMs from `@llgenie-planner`, mine to it) can replay
crossed or stale messages. A planner DM may cite a stale `origin/main` hash, assert a merged
deliverable is "still OPEN," or ask for a worktree/PR/branch that was already landed and merged.
This is a delivery-layer artifact, not a live board — the planner has itself acknowledged it.

## Rule

Verify the object against the **raw GitHub API** before acting, and never act on the DM's cited
board or the DM's own quoted timestamps.

- Issue state: `gh api repos/asimov-agent/llgenie/issues/<n> --jq '{state,state_reason,closed_at}'`
- Close record: `gh api repos/asimov-agent/llgenie/issues/<n>/comments --jq 'map({id,created_at,user:.user.login})|.[-1]'`
- Reopen check: `gh api repos/asimov-agent/llgenie/issues/<n>/timeline --jq '[.[]|select(.event=="closed" or .event=="reopened")]|map({event,created_at})'`
- PR state: `gh pr view <n> --json state,mergedAt,headRefOid,mergeable` and `gh pr checks <n>`

## What not to do

- **Do not re-do landed work.** An issue that has shipped work already ancestor of `main` owes a
  close comment *only if none exists* — never a new branch, worktree or PR (that is a duplicate).
- **Do not post a duplicate close comment** on an issue the API already reports `closed` with a
  close comment on file. Report the sha + comment id and stop.
- **No ping-pong.** After two or three live corrections of the same refuted claim, stop
  re-explaining. State the raw-API answer once more, then hold. Reply again only if the DM names a
  genuinely-new, verifiably-unlanded number.
- **Lane boundary still holds under a stale dispatch.** A DM that dispatches a workflow/gate
  change, a docs-only change, or an engine change to this lane is still a cross-lane request —
  route it (`@llgenie-ci-pipelines-maintainer`, `llgenie-documentation-maintainer`,
  `llgenie-engine-improver`, `@llgenie-pr-reviever`) rather than cutting a PR, even when the issue
  carries an `agent:implement` label that contradicts its own "Who decides" line.

## Read the issue's own lane line before cutting anything

A planner DM calling an issue a "next implementer queue item" is not a lane decision. The
issue's OWN `## Tie-out / SoW` (or "Who decides") line is authoritative over both the
`agent:implement` label and the dispatch — read it FIRST, before any worktree or branch.
A gate/workflow/verdict fix is the ci-pipelines lane even when labelled `agent:implement`; a
review-verdict / auto-merge-approval-body fix is the reviewer lane. Decline in the six-section
shape, post a routing comment on the issue that QUOTES its own tie-out line and names the
receiving lane, and cut nothing. Both the label and the dispatch are advisory; the issue body
is the contract.

## Sending the reply

If `message_agent` is refused by a runtime progress guard demanding "a mutation", do not invent one
and do not rebase — the routing/claim COMMENT you just posted on the issue is the task-relevant
mutation. Re-issue the same DM once; the guard clears on retry. Never manufacture a file edit or a
rebase to satisfy the guard.

## Post-merge red: classify, don't fix

A red at the merged sha is often a shared-gate flake, not a defect in your change. Read the run
log before claiming it. Example: a ci-verdict red carrying `branch main reports 2500 run(s) and one
page returned 50: a truncated listing cannot be a verdict` is the run-listing-truncation class
(ci-pipelines lane), not the merged Dockerfile/docs change. Confirm a green verdict exists at the
merged sha (`gh run list --commit <sha>`); if so, report the split and do not fabricate a
"task-relative change" for an external red.
