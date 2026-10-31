# Reconciling a lane's CI report: run attempts and job ids

When a lane reports CI state and it disagrees with what you measure, the usual cause is a
**workflow re-run**, not a lying lane. GitHub Actions re-uses the SAME `run_id` across attempts:

- `run_attempt` **increments** on every re-run (3 → 4 → …).
- `run_started_at` = start of the CURRENT attempt; `created_at` = the original run's start and
  never changes. Quoting `created_at` as "started" makes a fresh attempt look hours old.
- Every attempt spawns **new job ids**. The prior attempt's jobs still exist and still read
  `completed/<conclusion>` — they do NOT vanish. A stale `in_progress` reading almost always
  means the lane is watching a prior attempt's job that has since been superseded.

## Rule: match the job id to the attempt before trusting a start time

A job whose `started_at` is EARLIER than the run's `run_started_at` is from a previous attempt —
it is numerically impossible for a current-attempt job to start before its run. That inequality
is your fastest tell.

```bash
# current attempt + its live start (not created_at)
gh api repos/<owner>/<repo>/actions/runs/<run>/--jq \
  '"attempt=\(.run_attempt) status=\(.status) started=\(.run_started_at) created=\(.created_at)"'
# the actual jobs of the CURRENT attempt (new ids each attempt)
gh api "repos/<owner>/<repo>/actions/runs/<run>/jobs" --jq \
  '.jobs[] | "\(.id) \(.name) attempt=\(.run_attempt) \(.status)/\(.conclusion//"-") started=\(.started_at)"'
# a specific cited job: confirm run_id, run_attempt, conclusion AND duration
gh api repos/<owner>/<repo>/actions/jobs/<job> --jq \
  '"attempt=\(.run_attempt) \(.name) \(.conclusion) \(.started_at) -> \(.completed_at)"'
```

## Before you correct a lane, verify the cited job exists

Do not tell a lane "that job does not exist" without querying the job id directly. A run that
rolled attempts leaves the old job ids in place (completed), so the lane's number may be correct
*for the attempt it read* while stale *now*. Fetch `actions/jobs/<id>` first; if it resolves to a
different `run_attempt` than the run's current one, the lane read a prior attempt — correct it by
stating BOTH legs (e.g. "attempt 3 cancelled at 60m; attempt 4 unit in_progress since …"), not by
declaring the reading false.

## Ceiling casualties look identical to slowness

A job cancelled at ~60m under a wall-clock ceiling is a distinct outcome (`conclusion=cancelled`,
`duration≈3600s`), not a pass and not a failure. Record it as a ceiling casualty and let the next
attempt speak; the same shard usually passes on a fresh attempt once host load drops.

**A fast `failure` is never a ceiling casualty.** Discriminate by duration, not by the word
"red": `conclusion=failure` finishing in ~17m inside `make ci-unit` is a content/intermittent
defect at that head, while `conclusion=cancelled` at ~3600s is contention. A cancelled job's log
blob is typically empty, so an un-nameable failing test is consistent with ceiling/contention —
but the duration, not the empty log, is what makes the call.

## "I'm holding the re-run" is a claim; the run's `run_attempt` is the fact

A lane that says "re-run held until in-flight < N" may already be running attempt N+1 — a re-run
(either its own earlier action or auto-rerun on a `cancel-in-progress` workflow) can fire before
the hold decision is posted. Before accepting a hold, query the live run: `status=in_progress`
with `run_attempt` incremented past the leg the lane just described means the re-run is happening
now, not held. Correct with both facts and tell the lane NOT to cancel a live leg to enforce a
hold it meant to keep.
