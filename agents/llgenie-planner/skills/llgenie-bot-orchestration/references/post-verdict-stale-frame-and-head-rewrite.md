# Three sharp traps when re-verifying a lane's "ready" report

Measured 2026-11-05 on #1802/#1803. Each trap reads as a real gate but is not one; measure before you repeat or dispatch.

## 1. "waiting on the reviewer verdict → tick" can be a stale frame

An implementer that already has the review may still report the gate as pending ("ready for the
reviewer verdict → tick #N → owner merge"). The proof it is stale: at the current head, the fresh
CI run's `make check-pr-acceptance` step is **SUCCESS**. That step is the #1792 self-red, and it
clears exactly when the verdict tick lands on the closing issue. Measure:

```bash
gh api repos/<o>/<r>/actions/runs/<id>/jobs \
  --jq '.jobs[].steps[]|select(.name|startswith("make check-pr"))|{n:.name,c:.conclusion}'
```

If acceptance=success, the tick already happened — do **not** re-dispatch a verdict request.
Correct the stale frame once (on-issue comment + a DM naming the existing verdict comment id) and
let the in_progress run finish.

## 2. An `auto-merge: deferred <sha> (in_progress)` comment is NOT an arm

The auto-merge bot posts "Not auto-merged … head <sha> still has an unfinished run (in_progress)"
whenever the run hasn't finished. That comment reads identically to an armed auto-merge — it is
not. The fact is GraphQL:

```bash
gh pr view <n> --repo <o>/<r> --json autoMergeRequest --jq '.autoMergeRequest'
# null  => NOT armed (correct per #1088; only owner/queue merges)
```

Never report "auto-merge armed" from the deferral comment; quote the `autoMergeRequest` object or
`null`.

## 3. A squash-rewrite head is verified by tree identity + merge-base, not commit count

When a lane rewrites its head to "one clean commit" (soft-resetting a transient empty
reconciliation marker into the real commit), `git log A..B` shows one commit and `git diff A B` is
EMPTY — that is a content-identical rewrite, not drift. Confirm content-current with:

```bash
git merge-base <head> origin/main        # == current main tip
git rev-parse <head>^{tree}               # == the previously-endorsed head's tree sha
```

`git rev-list --count <base>..<head>` == 1 is corroboration, never the sole proof. A new head sha
is not a new decision — an empty `git diff A B` across a rewritten head means the lane changed
history, not content.
