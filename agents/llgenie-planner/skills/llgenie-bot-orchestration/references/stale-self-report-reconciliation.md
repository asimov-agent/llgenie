# Reconciling a lane that echoes its own stale report

A lane's report is a claim; the API is the evidence. The hard case is a lane that repeats, across turns,
a status it already gave — that repetition is one observation aged, not a second read.

## Rule

**A fact a lane stated in an earlier turn is still one read.** When a bot answers with the same
"live vehicle" PR, the same `main` sha, or the same "owner-merge-ready" status it gave a turn ago, re-measure
at the API in the pass that consumes it. If the current API now contradicts it (the PR merged, the owner
closed it unmerged, `main` advanced), the lane's next message will keep echoing the stale fact until the
board itself says otherwise.

## Procedure

1. **Measure, don't relay.** Before you repeat any lane status to the owner, read the live object:
   `gh pr view <n> --json state,mergedAt,mergeCommit,mergeStateStatus,headRefOid` and
   `gh api repos/<owner>/<repo>/commits/main --jq .sha`. A closed-unmerged PR can still carry a
   planned `merge_commit_sha` — trust `merged_at`, and confirm the merge landed with
   `git rev-parse --is-ancestor <sha> origin/main`.
2. **Correct on the board, not the DM.** Post the authoritative state as a comment ON THE ISSUE with the
   sha and the minute you measured. A correction delivered only in a DM does not exist for the next reader;
   the issue timeline is what makes the lane's following message converge.
3. **Reconcile disagreement against the API, never each other.** When two lanes report different states for
   one PR, the API and the issue timeline are the source of truth — do not let two memories argue.
4. **Close with a durable artifact, not more chat.** Land the finding as a refined issue in the repo's
   six-section shape (Defect / Repro / Why it matters / How we fix it / Acceptance / Who decides / Out of scope),
   and verify it opened (read it back with `gh api .../issues/<n>`). `gh issue create` has no `--json` flag —
   it prints the URL; confirm the number via an API read-back. A guard asking for "a task-relevant change" is
   satisfied by the on-GitHub record, never by narration.

## Why

A lane acts on its snapshot; if the planner relays that snapshot instead of the current API, work gets routed
onto a merged PR, a dispatch is pointed at a closed vehicle, or a duplicate branch gets cut — all avoidable
with one same-pass read. The board comment is the mechanism that stops the echo: it gives the lane a newer
fact to read than its own memory.
