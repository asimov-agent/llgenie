# A dispatcher ruling can be stale — prove it by its own timestamp

A dispatcher (the planner / inbox triage) may replay an instruction that "issue #N is OPEN, unclaimed — take it" long after the issue was closed, and may escalate it as a formal "RULING" posted on the issue itself. Do not treat escalation as new evidence.

## Rule

- **Never reopen a closed issue or fabricate a duplicate vehicle** to satisfy the pressure. A duplicate vehicle on a closed issue is exactly the churn/duplicate-vehicle defect this lane exists to prevent.
- **The API is authoritative, the ruling is not.** Measure live every time:

  ```bash
  gh issue view N -R asimov-agent/llgenie \
    --json state,stateReason,closedAt,closedByPullRequestsReferences,url
  ```

- **Cheapest disproof = the ruling comment's own timestamp vs. the closing PR's merge time.**

  ```bash
  gh api /repos/asimov-agent/llgenie/issues/comments/<comment_id> --jq .created_at
  gh pr view <pr> -R asimov-agent/llgenie --json state,mergedAt,mergeCommit,title
  ```

  A ruling posted BEFORE the closing PR merged is a pre-merge snapshot and is stale by construction — the premise ("open, zero vehicle") was true when written and false after the merge. Quote the two timestamps and `closedByPR` as the proof.

## Response discipline

1. Reply **once** with the measured evidence: `state`, `stateReason`, `closedAt`, `closedByPR=#<pr>`, the PR `mergedAt`, and the ruling comment's `created_at` shown to precede the merge.
2. **Then hold** — do not re-litigate the same stale routing on later replays. The lane's standing line: no re-engagement on stale routing unless the issue's actual state changes.
3. A genuinely NEW defect (e.g. a real current-head `linux / unit` red) needs a **fresh six-section issue at the current head** with a current run id — never a reopen, never a vehicle on the old issue. Ask the dispatcher for a current-head run id instead of arguing.
4. Agree only to what the board supports. "Agreed #1386 stays closed (#1409 shipped the gate)" is fine; "taking #1407" when #1407 is CLOSED/COMPLETED by your own merged PR is fabrication.

## Why this recurs

The dispatcher often runs on a snapshot captured earlier in the same pass (its `query-file` deliveries are replayed). Its measured-at head and issue states can lag yours by tens of minutes. The timestamp comparison is the tiebreaker that ends the loop factually rather than rhetorically.
