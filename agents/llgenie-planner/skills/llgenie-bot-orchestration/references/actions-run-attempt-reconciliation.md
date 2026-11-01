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

## Rule: `commits/<sha>/check-runs` returns EVERY attempt — dedupe by name, newest wins

One sha can carry **several check-runs with the SAME name**: a recheck re-runs a gate, and a gate
plus its companion (`verdict` + `recheck`) both report. A naive
`select(.conclusion=="failure")` on that list therefore reports a red that a LATER run at the same
name already superseded — a merge tip can read `fail:[verdict] inprog:[recheck]` while a separate
`verdict` run at the *same* sha is `success`. Filing a post-merge defect on that reading is a false
positive against the owner's merge.

Resolve the **deciding conclusion per name**: take the run with the latest `started_at` (fall back to
`completed_at`), and only call the gate red if that newest run is `failure`:

```bash
gh api "repos/<o>/<r>/commits/<sha>/check-runs" \
  --jq '.check_runs|map({n:.name,c:.conclusion,s:(.started_at // .completed_at // "")})
      | sort_by(.s) | group_by(.n) | map({gate:.[0].n, latest:.[-1].c, all:[.[].c]})'
```

`all:[success, failure]` with `latest:success` is a transient recheck that failed and was superseded —
report it as "merged through a transient recheck; deciding leg green", never as "main is red at the
merge". Only `latest:failure` (or a still-`null` latest with nothing completed) is a real deciding red.

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

## Rule: a red-count that filters FAILURE/ERROR reads `cancelled` as green

`gh pr checks <n> --json state` returns a `state` that includes `PENDING`, `SUCCESS`, `FAILURE`,
`ERROR`, **and `CANCELLED`**. Counting only `FAILURE`/`ERROR` therefore reports `0 red` on a PR
whose only unresolved leg is `linux / unit = CANCELLED` — the exact "green is not mergeable" trap.
Never reduce a PR to a red-count; enumerate the checks and require the load-bearing leg be
`SUCCESS`:

```bash
gh pr checks <n> -R <owner>/<repo> --json name,state \
  --jq '.[] | "\(.name)=\(.state)"'
```

A PR is merge-ready only when every leg reads `SUCCESS` — `CANCELLED` on `linux/unit` means the
suite never produced a verdict, so "0 failing checks" and "ready" are different claims.

## Rule: rebase ONLY when the PR is CONFLICTING — "behind main" is not a rebase trigger

An open PR is 1-behind main after **every** merge, so `MERGED`-then-advanced base is the normal steady
state, not a defect. A `MERGEABLE`-but-`UNSTABLE` PR (base behind, some check red) is **not** rebased on
every main move — demanding one is a planner mis-application, and it churns the head, voids the green
you already had, and re-triggers review. The single rebase trigger is `mergeable=CONFLICTING` /
`mergeStateStatus=DIRTY` (a DIRTY PR gets **no CI run at all**, so nobody else will un-stick it).

When it IS conflicting, name the conflict before dispatching — the rebase lane should resolve one file,
not re-author a PR:

```bash
H=$(gh pr view <n> -R <o>/<r> --json headRefOid --jq .headRefOid)
git fetch origin "$H" origin main --quiet
git merge-tree $(git merge-base "$H" origin/main) "$H" origin/main | grep -A2 '^changed in both'   # the SAME files on both sides
```

A rendered **index file** (e.g. `CHANGES.md` / a change-notes index) is the routine conflict: both the
PR and the merges since it branched append a row. Resolve by **keeping both entries** — main's rows are
immutable, the PR's row is appended — and tell the lane explicitly not to re-author the PR's own payload
files (byte-identity folds, generated docs) while rebasing; a rebase that rewrites the payload destroys
the property the PR was verified for. Then require `--force-if-includes` after a fresh fetch, and a
re-run at the NEW head (a green at the pre-rebase head binds to that head only).

(Genuinely merge-ref-dependent reds still want a fresh head — but prefer the narrowest route: if the red
is `CANCELLED` *and* the PR is not conflicting, re-run rather than rebase; a rerun replays the stale ref,
so when the gate truly depends on the merge ref the rebase is justified — say which of the two you
measured, and never prescribe a rebase from "main moved" alone.)

## "I'm holding the re-run" is a claim; the run's `run_attempt` is the fact

A lane that says "re-run held until in-flight < N" may already be running attempt N+1 — a re-run
(either its own earlier action or auto-rerun on a `cancel-in-progress` workflow) can fire before
the hold decision is posted. Before accepting a hold, query the live run: `status=in_progress`
with `run_attempt` incremented past the leg the lane just described means the re-run is happening
now, not held. Correct with both facts and tell the lane NOT to cancel a live leg to enforce a
hold it meant to keep.
