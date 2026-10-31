# Approvals, auto-merge, and where a branch must live

## A review must come from a different identity than the author

If every bot pushes with the same token, every PR's author is that account and GitHub refuses its own review:

```
gh pr review <n> --approve  ->  GraphQL: Can not approve your own pull request
```

Two ways out, in order of preference:

1. **The workflow's own token.** `github-actions[bot]` is a *different* account from the human whose PAT pushed the branch. With `permissions: pull-requests: write` on the approving job it can approve a PR authored by that human. The guard is "approver ≠ author", not "use token X".
2. **A second identity's PAT**, used for approve and merge.

Constraint that makes (1) workflow-specific: a `pull_request` run **from a fork** gets a read-only token and no secrets, so the approve/merge step belongs in a `workflow_run` workflow that executes in the **base** repository.

A bot cannot approve a PR its own bot account authored — keep the approver-≠-author check explicit and test it.

## Cross-repo (fork) heads lose secrets and the approval path

```
gh pr view <n> --json isCrossRepository,headRepositoryOwner
```

A `pull_request` run from a fork receives **no repository secrets** and read-only permissions; that is why such repos need a `workflow_run` merge workflow at all.

**But do not infer "cross-repo ⇒ unapprovable".** That is a rule of thumb, and acting on it sends a lane to re-push a branch for a blocker that does not exist. Measure instead:

```
gh api repos/<owner>/<repo>/collaborators/<identity>/permission   # admin|write|read
gh pr view <n> --json reviews,reviewDecision,autoMergeRequest
```

A collaborator with `write` or `admin` can approve a fork PR; `REVIEW_REQUIRED` with `reviews: 0` then means only that the approve step has not run yet (it waits for CI to conclude). The real fork costs are the read-only token and the absent secrets — re-push for *those*, when a leg needs them.

Default for agent-created work: **branch and push in the canonical repo**, keep the fork for external contributors. Migrate opportunistically — a new same-repo branch from the same commit plus a fresh PR is enough; the old cross-repo PR closes with a comparison.

## The repo switch is admin-only and it is a real gate

```
gh api repos/<owner>/<repo> --jq .allow_auto_merge        # check
gh repo edit <owner>/<repo> --enable-auto-merge          # enable (needs admin)
gh api -X PATCH repos/<owner>/<repo> -F allow_auto_merge=true
```

A `write` token returns **404** on the PATCH — that is a permissions gap, not a missing feature; the owner must click Settings → General → Pull Requests → Allow auto-merge. Without it `gh pr merge --auto` is refused outright.

## Arming is a delegation of merging, not a merge

```
gh pr merge <n> --squash --auto      # arms it; lands only when checks pass
gh pr view <n> --json autoMergeRequest,mergeStateStatus
```

Arm every PR you would merge on green, then leave it: the workflow approves only on `conclusion == 'success'` and merges `CLEAN` only. Read the state honestly — `BLOCKED` usually means `REVIEW_REQUIRED` (which the approve step clears), while `CONFLICTING`/`DIRTY` means a rebase.

Never arm/merge on a moving job count, and never bypass with `--admin` (a `write` token cannot, and it would defeat the gates).

### Read the arm back with the right field, and require green at the SAME head

`gh pr merge --auto` exits 0 whether or not it armed, so the exit code is not the fact. Read it back — with the field that actually exists, or a null reads as "disarmed" and you will report a phantom regression:

```
gh api repos/<o>/<r>/pulls/<n> --jq 'if .auto_merge then "ARMED \(.auto_merge.merge_method)" else "null" end'
gh api graphql -f query='{repository(owner:"<o>",name:"<r>"){pullRequest(number:N){autoMergeRequest{enabledAt mergeMethod}}}}' \
  --jq '.data.repository.pullRequest.autoMergeRequest'
```

The REST shape has no `.auto_merge.enabled_at` — reading it returns empty and manufactures a false "it disarmed after the push". Confirm with both APIs before telling anyone a PR is unarmed, and quote the `enabledAt` you read back.

**Two independent conditions, at one head.** `mergeable` and `green` are separate facts and both must hold *at the head that will merge*. Any push — rebase included — creates a new head and **voids the previous run's verdict**: a green unit pass at the pre-rebase sha proves nothing about the rebased tree, so a just-rebased PR is "mergeable but not yet green" and arming waits for its own run. The converse bites too: a green PR can sit `DIRTY` with **no CI run at all**, because a conflicting PR never gets one — which is why "all checks green" and "ready to land" diverge.

## The merger can starve itself

A `workflow_run` merge sweep keyed `group: <workflow>-${head_branch}` with `cancel-in-progress: false` queues **one sweep per CI completion** and none supersedes the last. On a busy repo the merger becomes a large slice of the queue and waits behind the very runs it is meant to act on — armed PRs sit `BLOCKED` while the sweep starves.

Check before blaming approvals: `gh api '…/actions/runs?status=queued'` and group by workflow name. Fix: `cancel-in-progress: true` for the sweep group (each sweep re-reads current PR state, so a later one legitimately subsumes an earlier one), plus a test pinning the concurrency block's shape so a harmless-looking setting cannot regress it.

Which vehicle survives when several PRs carry the same skeleton is a separate decision — see `references/vehicle-selection.md`.

## A green PR that cannot be approved is a mechanism bug, not a review queue

When N PRs sit at "BLOCKED / REVIEW_REQUIRED" with all checks green, stop telling the owner to approve them one by one and ask instead: *which identity is allowed to approve here, and does it exist on this head?* The answer is usually structural (same identity, fork head, or an approval step nobody wired).

## Close the issue when its fix merges

An issue left open after its fix lands makes every later brief quote a tree that no longer exists — three lanes will re-report the same "red main" for hours, and each will spend a turn re-deriving a fact that changed. Close with the merge sha in the comment.

## Every brief carries the state it was measured from

Format dispatches as `main=<sha> measured <HH:MMZ>` plus **PR heads beside PR numbers**. Nearly every disagreement in a fast-moving session is a stale read, not a disagreement about the work: the sha plus a command anyone can re-run ends it in one turn. Same rule for findings: quote the ref it ran on as well as the sha.
