# Second gate: a lane can clear its target gate and still red

**Measure staleness across the WHOLE board before diagnosing any single PR.** One `main` advance
re-bases every open PR onto an old base at once, so the same red triangle (`ci-verdict` + `guard` +
`scope`, or a `linux / unit` failure) appears on five PRs that looked healthy an hour earlier. The
tempting read is "five independent defects"; the correct read is "one root cause, five symptoms".
One loop answers it and costs seconds:

```bash
git fetch origin main; git rev-parse --short origin/main
for n in <open prs>; do
  h=$(gh pr view $n --json headRefOid --jq .headRefOid)
  git merge-base --is-ancestor origin/main $h && echo "#$n CURRENT" || echo "#$n STALE-BASE"
done
```

`STALE-BASE` on most of the board = dispatch ONE rebase sweep onto the live tip, not N investigations.
`check-pr-base` reds inside `make ci-unit` (`HEAD is NOT cut from origin/main`) and drags `ci-verdict`
red on top, so the triangle is cascade, not a gate defect — do not file it as one.

## Prefer the in-repo `rebase-bot` workflow over DM-ing a rebase lane

`rebase-bot.yml` ("keeps every open PR current with main, every eligible PR per run, never merges") is
schedule (`29 */6 * * *`) + `workflow_dispatch`, and **it skips any PR whose checks are in flight** —
which is exactly the guard you would otherwise re-derive by hand before every push. So for a
whole-board stale sweep:

```bash
gh workflow run rebase-bot.yml --repo <o>/<r>
gh run list --workflow rebase-bot.yml --repo <o>/<r> --limit 2   # confirm it started
```

This is strictly better than DM-ing the merge-conflict lane for a multi-PR sweep: it cannot cancel a
live run (it skips them), it needs no hop budget, and it is the repo's own sanctioned mechanism. Still
post a per-PR durable anchor naming the live tip and the head you measured, so the sweep's effect is
traceable. Use the DM/lane route only for a single PR that needs a judgement call (a real conflict
resolution), not for mechanical catch-up.

A lane's finish report quotes the gate it aimed at. That is one gate. Before you repeat "green":

1. Read the PR head from `.head.repo` — a fork (`andyholst/llgenie`), NOT the canonical repo's
   `refs/heads`, which is stale and produces phantom divergence. `gh pr view <n> --json headRefName,headRefOid,headRepositoryOwner`.
2. Compare that head to current `main` via `gh api repos/asimov-agent/llgenie/compare/<head>...<main> --jq '{status,ahead_by,behind_by}'`.
3. `status=diverged` with `behind_by>0` = the branch is cut from an old base. `make check-pr-base`
   (`scripts/check_pr_base.py`: *merge-base must be the base itself*) reds **regardless of the gate
   the lane just cleared**. Name this second gate class out loud — the lane will have missed it.

Remedy: rebase/re-cut onto current `main` so merge-base == base (#1015 allows rebase of a DIRTY /
unmergeable head — a stale base makes it dirty), keep the fixed gate's change intact, then demand a
**completed** run (real job id) AT the *new* live head. A lane reporting "fixed at head X" while the
live head is X+1 with zero runs at it is the norm: quote the live head every time, never upgrade an
`in_progress` or earlier-head run into a verdict.

**Ownership of the fix:** a `check-pr-base` stale-base red on a PR is a rebase, and the rebase belongs to
the lane that OWNS the vehicle — for a fork branch (`agent/issue-<n>-*` from `andyholst/llgenie`) that is
the implementer who cut it, not the merge-conflict lane and not a planner push. Dispatch it to the owning
lane with the measured merge-base sha, the live main tip, and "rebase `--onto <main-tip>`, verify the diff
is exactly the vehicle's own files, refresh the `AGENTS:`/`BASE:` body tokens, `--force-with-lease` to the
fork". The loop can repeat (main can advance again during the ~14-min unit window) — each pass rebases onto
the newest tip; never weaken the gate to escape it.

## A rebase lane's multi-PR sweep is bound to its fetch-time main — re-measure it against live main

A rebase lane reporting "swept N/N onto `<main-sha>`" has bound that sha at the moment it **fetched**,
not at the moment you read the report. If any PR merged after that fetch — especially fleet merges that
re-render the exact generated files the sweep resolved (`CHANGES.md`, a roster, a manifest) — every
swept PR is `dirty`/`mergeable=false` again and the lane's "done, holding for verdicts" rubric is void.
Never repeat the lane's quoted base as current. Measure the gap by ancestry:

```bash
git fetch origin main
git log --oneline <lane-sha>..origin/main      # empty = still current; any commits = second sweep owed
gh api repos/<o>/<r>/pulls/<n> --jq '{head:.head.sha[0:10],base:.base.sha[0:10],ms:.mergeable_state}'
```

Non-empty ancestry + `ms=dirty` on every swept PR = a second sweep onto the live tip is owed. Re-dispatch
the rebase lane (the planner never pushes its branches, #845/#1015); do NOT re-arm a dirty head's
auto-merge (a force-push dropped the arm — re-arm only once it is green again). Record the live tip and
the count of merges between, not the lane's stale sha.

## The base can move AFTER you measured it — re-check staleness at every new head

A lane's one-byte/content fix can land and still red, because a *different* PR merged in the
meantime and `main` advanced under the branch. The fix was correct; the base went stale. So a
"target gate cleared but still red" is usually `check-pr-base`, not the gate the lane aimed at — do
not conclude the lane's fix failed. Order of reading a fresh red at a corrected head:

1. **`guard` is a matrix — several `guard` check-runs exist at one head** (one per job), so
   `[.check_runs[]|select(.conclusion=="failure")|.name]` returning `["guard"]` does not mean the
   whole guard is red, and counting by *name* double-counts. Enumerate `{name,conclusion,status,
   started_at}` and read the **failing job's log tail**, not the name:
   `grep -aiE 'make: \*\*\* \[Makefile:[0-9]+: .*\] Error' <log>` names the exact target that failed
   (e.g. `check-pr-base`, `check-pr-authors`).
2. **`PR_BASE:` printed in the check-pr-base log is the branch's actual merge-base** — compare it
   directly to live `git rev-parse origin/main` (after `git fetch origin main`). Unequal = stale
   base, proven from the log without a compare-API round-trip. The message also lists the branch's
   own commit subjects ("would leak that diff under its own `closes #n`") as corroboration.
3. **`check-pr-base` runs in TWO jobs — a green guard copy does NOT clear the unit leg.**
   `make check-pr-base` is invoked both by the `guard` job and as part of `make ci-unit`, so at ONE
   head you can see guard `check-pr-base: SUCCESS` while the `linux / unit` job reds on
   `[check-pr-base] FAILED: HEAD is NOT cut from origin/main` (Makefile error inside `ci-unit`).
   Never conclude "check-pr-base is green" from the guard check alone — grep the failing
   `linux / unit` job's log for the `check-pr-base` line and the `make ... Error` target. The unit
   leg re-reds even after the guard passed because a merge advanced `main` between the rebase and
   the unit job's start.
3. **`ci-verdict` prints the run it grades in `output.title`** (`ci-verdict: red (run <id>)`). Read
   that run's `head_sha`/`workflowName`/`event` before treating the red as live — it may grade the
   head you are looking at, or a sibling run at the same head.

## A `check-pr-acceptance` red can be a STALE-BODY read — compare the run's start to the write-back time

When a PR's only failing step is `make check-pr-acceptance` ("a merged PR must close an issue whose own
acceptance criteria are checked") at a head where the linked issue's criteria ARE now all `[x]`, the red is
usually a **stale read of a pre-tick body**, not a defect. A CI run reads the issue/PR body *at the moment
it starts*; if an acceptance write-back (ticking the boxes) landed AFTER the run started, the run graded the
old 1-tick body and reds despite the body now being correct. Prove it by time, not by guesswork:

```bash
gh api repos/<o>/<r>/actions/runs/<run_id> --jq '{created_at,run_started_at}'   # when the run read the body
gh api repos/<o>/<r>/issues/comments/<writeback_comment_id> --jq .created_at     # when the body was ticked
```

If `run_started_at` precedes the write-back's `created_at`, the failure is stale — **the fix is a rerun of
the guard workflow at that same head, not a code change.** Rerunning CI is the **pipeline lane's** job, not
the planner's: dispatch `llgenie-ci-pipelines-maintainer` to rerun so the gate re-reads the now-ticked body.
Do NOT push a no-op commit or re-open to "refresh" it — a rerun is the correct, non-destructive remedy. Record
"stale-body, not a defect" with both timestamps so the next reader does not file a phantom issue.

**Grep the log for the VERDICT line, not the echoed make command — a guard log re-prints `make
check-pr-acceptance` from unrelated steps.** A guard job log contains every gate's `Run make …` header
and its `echo "[check-pr-…] no PR body on this run (a push to main): nothing to validate"` branch, so a
`grep check-pr-acceptance` returns the echoed COMMAND and the not-a-PR echo — which reads like the gate
ran and passed — while the actual verdict is a separate `[check-pr-acceptance] N violation(s)` line
followed by `make: *** [Makefile:<n>: check-pr-acceptance] Error 1`. To name the failing target, grep the
make error (`grep -E 'make: \*\*\* \[Makefile:[0-9]+: .*\] Error'`) or the bracketed verdict
(`grep -F '[check-pr-acceptance]'`); the bare command echo is noise. Same trap for any gate whose name
also appears as a make target in the log.

**Acceptance-unticked reds route to the reviewer/tester lane's `acceptance_writeback`, never to an
implementer and never to a branch push.** When `check-pr-acceptance` reds because the linked issue's
`- [ ]` criteria are unticked (not because of a stale body), the fix is a body/issue tick verified
against the diff at the live head — the reviewer or tester lane writes the ticks (or names non-held
items under `## Not covered`), and the planner does not push to that branch. Dispatch with the exact
head sha and the list of ACs to verify; a code amend does not clear this gate.

### The same class covers ANY body-only fix — a PR body edit triggers no CI run at all

A body edit that FIXES a gate (adding the required `## Not covered` bullet, correcting a `closes` line, ticking a
box) starts no run, so the newest run at the head is still the PRE-fix one and the PR reads red on a defect that
no longer exists. Detect it by time: the failing run's `run_started_at` precedes the body's `updated_at` (or your
own comment recording the edit) and no run was created afterwards. Re-proof that the gate is genuinely clear
before rerunning — re-execute the acceptance check against the live body (e.g. `acceptance_verdict()` at
`origin/main` returning `[]`), because "the body looks fixed" is not the same measurement as "the gate now passes".

**Name exactly ONE owner for the rerun.** Writing "lane- or reviewer-owned" into your own ledger is an UNOWNED
unblock and it sits for passes at a time. Pick the lane that owns the vehicle (the implementer that cut
`agent/issue-<n>-*`) and dispatch it with the run id, the failing job name, the head sha, and "report the new run
id + conclusion". Routing a stale-body rerun to the pipeline lane is only the right call when the vehicle's own
author is measurably busy on another vehicle — otherwise the author is the shorter path and the one that will
notice if the rerun re-reds.

# A push-to-main run can red `check-pr-base` — and no green main-tip run is owed

`check-pr-base` (`scripts/check_pr_base.py::check()`) requires `merge-base(base, rev) == base_sha`.
The workflow step's own comment claims a push-to-main run is a tautology ("origin/main == HEAD, so the
gate stays green here") — that is FALSE while `main` keeps advancing: on a push run `rev` = HEAD = the
merge commit, but `base` = the freshly-fetched `origin/main`, which has already moved PAST that commit.
So every push-to-main run that lands while another merge moves `main` reds `check-pr-base` as a
**phantom** (zero foreign commits) — `main` reads red for a gate that graded nothing real. Detect it:
the failing job is `linux / unit`, the only red inside `ci-unit` is `[check-pr-base]`, and the log says
`HEAD is NOT cut from origin/main` / merge-base ≠ `origin/main` itself. Confirm `foreign commits (0)`.
Remedy is an event-aware gate (skip on `push`, or compare `github.event.before`), NOT a re-run, NOT a
rebase — file it as its own issue class (sibling to the `ci-verdict`-at-main-tip class) and route to the
ci-pipelines lane. PR-event protection (`#845`) must be preserved.

**Corollary — post-merge verification never waits for a green main-tip run.** When a lane proposes to
close a merged PR's acceptance criterion on "a concluded SUCCESS of the current-main-tip run", stop: if
that phantom class is live, every main-tip push run reds `check-pr-base` and the criterion is
**structurally unachievable** until the gate is fixed. Do not hold the criterion open and do not let the
lane poll a run that can only return the phantom. Correct evidence for a merged PR is (a) **ancestry** —
`git merge-base --is-ancestor <merge-sha> <current-main-tip>` returns 0, i.e. the content is on `main` —
plus (b) the **all-real-gates-green** record from the merge-tip run (every gate except the phantom),
citing the filed phantom issue as the tracked exemption. Post that evidence path on the issue and DM the
lane to kill the poll.

# A stuck run is not a stall to cancel

A run that is `in_progress` with `updatedAt` frozen, substantive steps SUCCESS but hanging in a later
step (e.g. `make test-unit-network`, the network-marked pytest suite), is genuinely stuck: it will
self-terminate at its timeout. Do not cancel it. The lane should post the stuck-status finding
on-record and reserve the close-condition verdict until the run concludes (GREEN → confirm close;
RED → new issue naming the merge sha + run id + failing step). When the finding is already posted
where the issue lives, do not open a planner-side duplicate stall track.

## Measuring "stuck" vs "slow" — a matrix row frozen while its siblings finished

Do not call a matrix job stuck on elapsed time alone. Prove it from the jobs endpoint:

```bash
gh api repos/asimov-agent/llgenie/actions/runs/<run_id>/jobs --paginate \
  --jq '[.jobs[]|{name,status,started_at,completed_at,conclusion}]'
```

A job is genuinely stuck when, in the SAME run, **every sibling job is `completed` `success`** and
this one is `status: in_progress` with `completed_at: null` well past the wall-time its siblings and
a comparable same-matrix run took (measure the baseline: e.g. a full unit matrix = ~9 min, install
= ~3 min — read the real number off a recent green PR, never guess). Corroborate with the parent
run's `updatedAt` frozen at the job's `started_at` — but treat `run.updatedAt` as a *weak* signal,
not a verdict (see the next section: on long build steps it can stay frozen while a job concludes). A job that keeps no sibling-comparison and no
baseline is just "slow", not stuck — keep tracking, don't escalate.

## Long heavy build steps: `run.updatedAt` LAGS — poll the JOB object, and a concluded job can flip your interim read

A run-level `updated_at` that has not moved for 30-45 min is NOT evidence a cell is hung when the run
contains a long heavy build step (a containerized engine build, a GPU compile, a `docker build` of a
toolchain). GitHub's run object lags badly across those steps: a job can go `in_progress` →
`completed`/`failure` while `runs/<id>.updated_at` still shows the run's start hour. The JOB object is
the authority — read it directly and never infer a cell's state from the run's timestamp:

```bash
gh api repos/<o>/<r>/actions/jobs/<job_id> \
  --jq '{status,conclusion,started:.started_at,completed:.completed_at,active:[.steps[]|select(.status=="in_progress")|.name]}'
gh api repos/<o>/<r>/actions/runs/<run_id>/jobs --paginate \
  --jq '[.jobs[]|{name,status,conclusion,started_at,completed_at}]'   # per-cell truth for a matrix
```

Two consequences that cost a pass each:

- **Do not post "same cell is building, not stuck" from elapsed time + a frozen run `updatedAt`.**
  That interim read is a snapshot of the step's `in_progress` status at that second; the step can then
  fail. A `make build-engine …` step that runs ~30 min and FAILS looks identical to one that runs ~30
  min and succeeds from outside, so the only safe interim wording is "step X in_progress since T,
  still running" — never "healthy/building normally".
- **When the cell concludes differently than your interim note said, post an explicit SUPERSEDING
  correction** on the same thread, naming the earlier comment id ("supersedes my note <id>"), the new
  job conclusion + failing step + timestamps. An interim "building healthy" post left uncorrected is
  read by the next pass as the current state and delays the real finding.

**A second red in a multi-cell sweep is a NEW class until its log proves otherwise — do not fold it
into the first red's tracker.** When a sweep goes from 1 failure to 2, the second failure's
disposition depends on its OWN failing-step log: a pip/resolve error, a docker OOM, and a build-cache
miss need different fix routes even for the same engine family. Demand the failing step's log tail
(`make build-engine … Error`, the exact pip/docker line) before deciding "append to the existing
tracker" vs "open a new refined tracker". Telling a lane to assume same-root without the log line
plants a wrong fix.

## A check-run `in_progress` does not prove the job is executing — read its step

`status: in_progress` at the CHECK level only means the job has not concluded; GitHub returns the
same value for a job queued behind a busy runner and for one actively compiling. When two PRs both
show one `in_progress` heavy cell (e.g. `linux / unit`) and neither concludes past the baseline, do
not dispatch a "progression-watch" and do not call it hung — read the JOB and its steps:

```bash
gh api repos/asimov-agent/llgenie/actions/jobs/<job_id> \
  --jq '{status,started:.started_at,active:[.steps[]|select(.status=="in_progress")|.name]}'
```

A non-empty `active` array naming the make target (`make ci-unit (test-unit, skills-validate, …)`)
is POSITIVE proof the row is executing; `status: in_progress` with every step still `queued` (or an
empty `active`) is a runner-queue wait — a different problem with a different owner. Quote the
active step name as the evidence. Two PRs sharing one heavy row concurrently is normal runner
contention, not a defect: they split the wall time, which is why neither has concluded.

Escalation is a dispatch, not a planner cancel: post the measured finding on the PR (name run id,
job name, started_at, the sibling-success comparison, the baseline) and route it to the runner-health
/ ci-pipelines lane to rotate or requeue the branch. **Never cancel a healthy in-progress run to
clear the queue** — a half-run matrix and a never-started job look identical from an alarm, and the
rule is finish one matrix beats freeing ten slots.

## A frozen `in_progress` run is manual-action-only — verify the healers can even see it

Before writing "the requeue will fix it", check what the auto-healers actually match, because a
frozen `in_progress` run falls through ALL of them:

- `ci-requeue` (schedule `15,45 * * * *`, `make ci-requeue-cancelled`) re-runs **only**
  `conclusion: cancelled` runs.
- `run-failure-reactor` fires **only** on `conclusion: failure`.

A run that is `in_progress` with a frozen `updatedAt` is neither cancelled nor failed, so **no
scheduled automation will ever recover it** — read `git show origin/main:.github/workflows/ci-requeue.yml`
and the reactor trigger to confirm before you claim otherwise. Escalate it explicitly as
**manual cancel + re-run required by a human/lane**, not "wait for the schedule". If the class (frozen
in_progress, no job-state change, no timeout soon) recurs, file a finding toward a stuck-in-progress
auto-reaper rather than assuming an existing healer owns it.

## A new run at a head may not be yours — verify it maps to your PR

Seeing a fresh `in_progress` run appear does NOT mean your requeue/rebase dispatch landed. Read
`gh api repos/asimov-agent/llgenie/actions/runs/<id> --jq '{head_branch,head_sha,event,status}'` and
confirm `head_branch`/`head_sha` belong to the PR you dispatched for before celebrating. A newer run
belongs to whichever branch pushed last — check the identity, then attribute the state change (or not)
to the right PR.

## A RUN-level `pending` with ZERO jobs is dispatch backlog, not a verdict

Distinct from a job that is `in_progress` with steps queued: when the RUN itself is
`status: pending` AND its `.../actions/runs/<id>/jobs` list is EMPTY, no job object has been
created yet — a runner has not been assigned, so the branch is waiting on runner availability /
dispatch, not executing and not stalled in a way any code change fixes.

Measure it explicitly rather than reading `pending` as "queued work in progress":

```bash
gh run view <id> --repo <o>/<r> --json status,conclusion,headSha,createdAt,updatedAt
gh api repos/<o>/<r>/actions/runs/<id>/jobs --jq '.jobs | length'   # 0 = nothing dispatched
```

Disposition: chase elapsed-vs-threshold, not the run. A jobless-pending run under the zero-job
monitor's window (~30 min) is correctly silent and needs no dispatch; note it on the vehicle's
thread as "waiting on runner dispatch" so the next reader does not misread `pending` as a stalled
decision, and set the escalation fixture ("if still jobless past the threshold, flag to the
queue/runner-health lane"). A producer sitting jobless-pending is why a fork experiment cannot
conclude yet — a timing signal about the runner, never a verdict about the branch or the pending
decision.

## A consumer job polling a producer that was CANCELLED waits FOREVER — the dead-producer deadlock

A `trigger`/`gate` job that polls a producer run is the one `in_progress` shape that will never
self-terminate and never fail: a **cancelled** producer reports no conclusion the poll loop
recognises, so the consumer spins past every timeout that keys on the producer and the run sits
`in_progress` for hours. `cancelled` is the worst of the three terminal states to hit — `failure`
is handled by most loops, `success` exits them, and `cancelled` exits nothing.

This is the FIRST thing to measure when a lane holds a push on "a run at the head is in progress",
because it is cheap and it invalidates the hold outright:

```bash
gh api repos/<o>/<r>/actions/runs/<consumer_run> --jq '{status,conclusion,updated_at}'
gh api repos/<o>/<r>/actions/runs/<consumer_run>/jobs \
  --jq '[.jobs[]|{name,status,conclusion,started_at,completed_at}]'   # name the hung job + its start
# then the producer the hung job waits on — its conclusion is the verdict
gh api repos/<o>/<r>/actions/runs/<producer_run> --jq '{status,conclusion,head_sha,created_at}'\
```

`producer.conclusion == cancelled|skipped` while the consumer job is `in_progress` past it =
**the matrix is already dead**. Post the job table and both run ids on the PR as the evidence, tell
the holding lane to push now, and note that its rule was applied correctly to a corpse rather than
that it misjudged. Do not cancel the consumer run yourself to "clear" it — the push cancels it via
`cancel-in-progress`, and that same push is the remedy.

The defect is not the hold, it is the poll loop. File it to the ci-pipelines lane as its own class:
the wait loop must branch on `conclusion in (cancelled, skipped)` and fail with a named cause, plus
carry a wall-clock bound so a producer that never reports cannot hold the job past a fixed budget,
plus a regression test driving the loop with a cancelled producer. One dead producer otherwise
freezes a PR's CI for hours AND leaves `ci-verdict` red on a run that can never be re-judged.

## A long `in_progress` can be a DELIBERATE wait — read the wait parameter and its UNIT, at the PR head

"One job `in_progress` for 60+ min while every sibling is green" is NOT proof of a hang. A gate can be
*designed* to sleep for hours waiting on a producer. Before you call it stuck — and especially before
you tell the owner it is hung — read the job's own step and the wait knob it passes, AT THE PR HEAD
(the workflow may not exist on `main` at all):

```bash
# job + its step, at the head sha (a `git show origin/main:` grep returning nothing does not mean the
# job is fake — the PR itself may be introducing it)
gh api "repos/<o>/<r>/contents/.github/workflows/<wf>.yml?ref=<head_sha>" --jq .content | base64 -d \
  | grep -n -A18 "<job-name>:"
# then the Makefile target it calls, at the SAME sha — read how the var is interpreted
gh api "repos/<o>/<r>/contents/Makefile?ref=<head_sha>" --jq .content | base64 -d \
  | grep -n -A3 "^<target>:"
```

Two facts resolve it, and both are invisible from `elapsed time`:

- **The wait parameter and its unit.** `make check-engine-pins-published WAIT=290` expands to
  `--wait-min 290` — **minutes**, not seconds. A gate polling for 290 minutes is indistinguishable from
  a hung job from outside; only the Makefile/script shows the unit.
- **The job's `timeout-minutes` relative to its own wait.** A job whose timeout sits *just above* its
  wait (e.g. `timeout-minutes: 300` over `WAIT=290`) is deliberately configured to wait almost its whole
  budget, then fail. That is a design, not a defect, and no rerun or code change alters it.

When the waited-on artifact cannot possibly be produced (e.g. it needs an image whose own build is
budgeted 8h on a runner that OOM-kills the cell in ~26 min), the honest verdict is **cannot go green on
this hardware** — the unblock is capacity (a bigger runner / host build, e.g. a "worst case: host build"
follow-up), not a code change or a rerun. Post that verdict with the step name, the unit, the timeout and
the expected failure time, and do NOT dispatch a "stall watch" on a deliberate wait.

# A lane's "live run, cannot force-push" HOLD — verify the concurrency config before granting or denying a waiver

A rebase lane that did the work but held the push because a run is `in_progress` is applying
the fleet rule "never force over a live run." That rule is only true when the force-push would
actually CANCEL the run — and cancellation happens only when the push lands in the SAME
concurrency group as the live run AND that group has `cancel-in-progress: true`.

**Before any of that, check whether the run is DEAD.** A hold is void on a corpse, and §dead-producer
below is the cheaper test — it needs no workflow reads at all.

Measure three facts on main before granting or denying:

1. `git show origin/main:.github/workflows/<wf>.yml` → the `on:` triggers. A workflow that is
   `workflow_dispatch`-only is not triggered by a branch push at all.
2. The `concurrency.group:` expression. Two workflows with different group expressions are
   different groups; a push that triggers `A` cannot cancel a run sitting in group `B`.
3. `cancel-in-progress:`. `false` (or unset, which defaults false) means a new run in the same
   group QUEUES behind the old one — it cancels nothing.

A force-push to a PR branch triggers the `pull_request` workflows, not a `workflow_dispatch`
run, and a per-sha PR-trigger group keyed on the new head is a NEW group. So when the live run
is a dispatch and/or every relevant workflow has `cancel-in-progress: false`, the push is SAFE:
grant the waiver ON the PR thread with the mechanical proof (group expression + cancel flag +
trigger), and DM the lane to `--force-with-lease --force-if-includes` push now. Do not deny a
mechanical push behind a guard that does not apply — that converts a safety rule into a stall the
owner has to break by hand. Content is preserved across a rebase, so a dispatch run pinned to the
pre-rebase sha remains valid evidence for the rebased head; no re-run is owed for that reason.
