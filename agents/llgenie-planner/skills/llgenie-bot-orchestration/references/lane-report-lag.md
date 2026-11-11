# Lane reports lag the wire: stale settled replies and repeated premises

## The pattern
A lane's message is a snapshot of the moment it was *authored*, not the moment you read it. Three distinct
failures appear together in practice:

1. **Pre-merge reports on merged PRs.** A lane finishes a rebase/review, composes a detailed report naming an
   intermediate head, and the PR merges before the report is delivered. The lane then keeps waiting on CI at a
   head that is no longer the PR's head. A merged PR's `headRefOid` is immutable, so `gh pr view <n> --json
   state,mergedAt,headRefOid,mergeCommit` settles this in one call — do it before believing any head claim.
2. **Settled replies that pre-date your correction.** A `status: settled` reply may arrive *after* your
   corrective DM yet reference an older process id, i.e. it was authored before your message landed. It will
   repeat the premise you already disproved.
3. **"in_progress" claims on concluded runs.** Lanes describe a run as in progress long after it concluded
   `failure`. Always read the run: `gh api .../actions/runs/<id> --jq '{status,conclusion,head:.head_sha[0:10]}'`.
   A watcher armed on a concluded run can only ever report that recorded outcome — tell the lane to kill it.

## What to do
- Verify on the wire first (`gh pr view`, `gh api .../runs/<id>`, `gh api .../issues/comments/<id>`), then correct
  with the measured ids in the same message. Quote the run id, the head sha and `status/conclusion`.
- **Do not resend a correction that is already queued.** When a lagging duplicate arrives, the queued message is
  already in the lane's inbox; answer the duplicate with silence (or one line acknowledging the batch) and let the
  lane process the earlier correction. Re-sending creates ping-pong and two competing narratives on the wire.
- Accept the good parts explicitly. A lane that re-ran a suite at the current head and posted real evidence
  (comment id verified by length) is doing the right thing even if another premise in the same message is stale —
  say so, then correct only the wrong premise.
- Every correction ends with the live queue: the issue id, the scope and the expected next report line. A
  correction that does not say what to do next teaches the lane to guess.
