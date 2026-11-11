# Red-signal triage: is this a real red, or expected downstream noise?

Companion to `references/verifying-lane-claims.md` (which covers a lane lying) and
`references/board-write-readback.md` (posting a board mutation and proving it landed by object id).
This file covers
the opposite failure: the planner or the AR shadow re-reports a red that is a stale measurement or a
gate working correctly, and pays a round-trip for it.

## A status that never changes under re-polling is NOT slow — read the failing step once

A loop of `gh run view <id> --json status` returning the same `in_progress` (or the same `fail` name) N
times in a row is not evidence of a slow job; it is evidence that **the field you are polling does not
carry the diagnosis**. Stop the loop after the second identical reading and spend one call on the failing
step instead:

```bash
gh run view <run-id> --json jobs --jq '.jobs[]|select(.conclusion=="failure")|.name'   # which job
gh run view <run-id> --json jobs \
  --jq '.jobs[]|select(.name=="<job>")|.steps[]|select(.conclusion=="failure")|.name'  # which STEP
grep -E "\[check-|violation|::error|make: \*\*\*" <(gh run view <run-id> --log)                 # the line
```

The step name is what assigns the cause. A job that hangs near its own bound (a wait loop polling a
peer, a readiness probe) reads `in_progress` for its whole limit and then `failure` with a message that
names the real reason — polling it a dozen times produces a dozen identical lines and zero information,
while the job's own log line names the defect on the first read. Equally, a `fail` check name that
repeats across polls has a *different* failing STEP underneath at each new head, so the name never
changes while the cause does.

Two concrete corollaries:

- **Do not poll an `in_progress` job to learn whether it will pass.** Read its current step list and its
  last log lines; a step that is inside a bounded wait prints the bound and the thing it waits on, which
  tells you the outcome class before the job concludes.
- **A run stuck `in_progress` well past its normal duration is itself the finding.** Compare against the
  same workflow's usual timing (a two-minute job sitting thirty-plus minutes) before assuming "still
  running" — the defect is usually a wait bound expiring slowly, and the fix belongs to the workflow, not
  to another poll.

## A lane's "no run id yet / I'll report when it lands" is a claim about a moment — measure now

A lane that opens a PR and reports "the dispatch just fired; I'll report the guard run id when the
check lands" is describing the moment it pushed. The run frequently HAS landed and red within a minute.
Accepting the "pending" framing at face value relays a dead claim and delays the fix. Measure the head's
rollup and read the actual job log before repeating "still pending": prefer the `detailsUrl` on each
`statusCheckRollup` red entry (it carries `.../actions/jobs/<job_id>` directly), and fetch the log with
the raw logs URL. A guard job that reds on one early step (e.g. `check-pr-openspec-change`) TERMINATES
the job before later steps evaluate, so a single red row can be one root cause, not the whole picture —
read the log, do not infer from the check name.

## `gh run list` has no `--head` flag — resolve a head's runs by `--branch` or the API, and read the rollup as a UNION

`gh run list --head <sha>` errors `unknown flag: --head`. To find the runs at a specific head, use
`gh run list --repo <o>/<r> --branch <branch> --json databaseId,headSha,status,conclusion,createdAt`
(each row carries `headSha`) or the direct API
`gh api "repos/<o>/<r>/actions/runs?head_sha=<sha>"`. Do not burn a call guessing a flag; `--head`
does not exist on `gh run list` or `gh run view`.

When SEVERAL runs sit at ONE head (multiple workflows, and/or multiple attempts of the same workflow),
the PR's `statusCheckRollup` is their UNION — a `guard FAILURE` row can belong to run A while
`scope SUCCESS` belongs to run B at the same sha. So "the rollup is red" is NOT "one run failed":
resolve each red to its own run id + `head_sha` and read the failing STEP before judging. A single run
at the head concluding `success` alongside two `failure` runs is gate- and workflow-specific (e.g. one
run's `check-pr-closing` red, another's `check-pr-acceptance` red), not a sha-wide red — classify each
run's own failing step, never the aggregate conclusion.

## One `guard` red can carry several INDEPENDENT causes — report them as separate fixes

The same failing `guard` job often contains more than one defect at once (a real gate defect plus an
acceptance self-red plus a cascade). Read the job log and enumerate every `make: *** [...] Error` /
`violation(s)` line, then attribute each to its own remedy. Reporting "guard red" as one item sends the
lane chasing a single fix while the PR stays red on the sibling. `scope` FAILURE beside a `guard`
FAILURE is usually cascade (no clean verdict published), not a second defect — the failing step's own
log line is the discriminator, never the check name.

## Your own earlier measurement is a claim about a moment too

A failure count you read at head A is evidence about head A, not about the PR. Before you contradict
a lane's "fully green" with "still `failure:3`":

```bash
gh api repos/<o>/<r>/pulls/<n> --jq '.head.sha, .base.sha[0:9], .mergeable_state'
gh api "repos/<o>/<r>/commits/$(gh api repos/<o>/<r>/pulls/<n> --jq .head.sha)/check-runs?per_page=100" \
  --jq '(.check_runs // .)[]|select(.status=="completed" and .conclusion!="success" and .conclusion!="skipped")|{name,status,conclusion}'
```

`status=="completed"` is load-bearing, not decoration — see the next section.

If the head moved since your read (a re-cut, a rebase push, a fresh commit from any lane), your counts
are stale and the lane is right — say so plainly and drop the contradiction. A stale contradiction
costs a round-trip and teaches the lane to distrust your corrections. Always stamp a red with the sha
it was measured at: `at <sha>: failure:3 — <named error line>`.

Corollary: a lane that answers with a *new* head and new run ids is not "looping", it is the writer
of the fix. Re-fetch before re-accusing.

## A fast lane can SELF-FIX between your diagnosis and your dispatch — re-fetch the head right before you post

An implementer watching its own CI will push a remedy for the red you just diagnosed (a self-introduced
`make lint` failure fixed by a one-byte trailing-newline commit two minutes after it landed). If you write
the dispatch off a head you read earlier, you route a defect that no longer exists and the lane replies
"already fixed" — a wasted round-trip and a credibility leak. Before posting any fix-dispatch, re-read the
head and its commits:

```bash
gh api repos/<o>/<r>/pulls/<n> --jq '.head.sha[0:10)+" "+.updated_at'
gh api repos/<o>/<r>/pulls/<n>/commits --jq '.[-3:][]|"\(.sha[0:10]) \(.commit.message|split("\n")[0])'
```

If the tip advanced past the sha your diagnosis cited, the diagnosis is stale history — reconcile it
("you already fixed X in `<new-sha>`") instead of dispatching the old defect. Both the start and the finish
of your own pass need the head re-read, not only the start.

## When the head advances, re-derive the failing GATE and the SCOPE CLASS — not just the same check name

A new commit does not merely re-run the same gate; it can change **which** gate runs and whether your
diagnosed defect is even selected. A pivot to a docs-only diff (a `.md`/reference/skill pointer) makes
`ci-scope` classify it `docs,skills`, so `linux/unit` is `skipped` — the pytest/unit defect you dispatched
against an earlier code head is no longer in the selected matrix at all. Meanwhile a *different* gate
becomes the sole red (`check-pr-base`, because the branch is still cut from a pre-merge base). So after any
head move, re-read the rollup and the failing STEP names and ask "is the defect I named still in scope?"
before re-routing it:

```bash
sha=$(gh api repos/<o>/<r>/pulls/<n> --jq .head.sha)
gh api "repos/<o>/<r>/commits/$sha/check-runs?per_page=100" \
  --jq '(.check_runs // .)[]|select(.status=="completed" and .conclusion!="success" and .conclusion!="skipped")|.name+":"+.conclusion'
```

State the scope finding to the lane explicitly ("new head is docs-only → `linux/unit` skipped, so the
unit defect from `<old-sha>` is no longer selected — confirm whether a code fix is still in the PR's
scope") so it does not chase a target the classifier dropped.

## A PR-BODY edit triggers NO run — a gate that reads the body keeps its pre-edit red in the rollup

Check-runs hang off a **commit**, not off the PR object. A lane that fixes a body-reading gate
(`check-pr-agents-line`, `check-pr-hygiene`, `check-pr-closing` — anything that greps the PR
**description**) by editing the body leaves `head.sha` unchanged, and GitHub does **not** fire a run for a
body edit. So the failing check-run at the head is still the one that judged the *pre-edit* body: the
content is fixed, the rollup is red. This is the body-side twin of the pre-write-back `guard` red above.

Tells, both cheap:

```bash
gh api repos/<o>/<r>/pulls/<n> --jq '.head.sha[0:10], .updated_at'     # head sha unchanged after a 'fix'
gh api "repos/<o>/<r>/actions/runs?head_sha=<sha>&per_page=3" \
  --jq '.workflow_runs[]|"\(.id) \(.event) \(.created_at[11:19])Z"'  # newest run predates the body edit
```

If the newest run at the head is older than the body edit, the red is **stale-by-construction**: do not
route it as a content defect and do not tell the lane to "add the line again" (it is already there). The
only unblock is a **fresh run at that head** — `gh run rerun <run-id>` or a trivial push — because the
gate reads the live body at run time and will pass. Say exactly that: "fixed in body, not yet green
on-wire; rerun clears it." The planner never reruns CI itself — hand the rerun to the owning lane.

Corollary for the board: "the fix is in the PR body" and "the PR is green" are different facts. Report
both, with the head sha and the newest run id, or the next reader re-dispatches a fix that already landed.
Also watch re-assertions: a lane citing a *completion comment* timestamped before your gate finding is
asserting against a stale state — verify the head and the newest run before accepting "ready for review".

## A docs/markdown-only commit's `make lint` red is usually `lint_linefeeds.py` — a one-byte fix

`make lint` (via `scripts/lint_linefeeds.py`) fails on a file missing a trailing newline, and a newly
added `.md` reference/pointer file is the common carrier. The log names the exact file; confirm the cause
from the log line, not the check name:

```bash
gh api --allow-escape-sequences repos/<o>/<r>/actions/jobs/<job-id>/logs \
  | sed 's/\x1b\[[0-9;]*m//g' | grep -A2 'LINT FAIL'

# LINT FAIL — files missing a trailing newline:

#   - <path/to/new/file.md>
```

`--allow-escape-sequences` is required or the logs endpoint 404s/BlobNotFound. The remedy is appending one
newline — route it as that, never as "the branch is stale" or "re-run CI".

## A check-run with `conclusion: null` is PENDING, not red — `conclusion != "success"` counts in-flight rows

`commits/<sha>/check-runs` returns every check at the head, including ones that have only just been
created under a running workflow. Those rows carry `status: in_progress|queued` and
`conclusion: null`. A red filter written as `select(.conclusion!="success")` therefore
**matches them**: a red list of `['record']` or `reds: 1` at a head whose every concluded check is
SUCCESS is the pending row, not a defect. Two consequences, both of which cost round-trips:

- You report a red that does not exist, and if you report it to a lane it chases a check that is
  already on its way to green.
- You re-report a *stale head's* real red as if it were current, because at the current head the same
  check name now appears as a fresh pending row — the name matches, the conclusion is null, and it
  looks like the red persisted. (A guard name repeats across the three per-workflow `guard` rows, so
  matching by name also collides.)

Discriminate on `status`, then on `conclusion`:

| Row state | Meaning | Action |
|---|---|---|
| `status=completed, conclusion=failure` | real red at THIS head | attribute per `references/red-signal-triage.md` buckets |
| `status=in_progress/queued, conclusion=null` | not yet a verdict | wait, or name the cell's identity; never red |
| `status=completed, conclusion=skipped` | gate chose not to run for this diff | not a red |

**A `skipped` row is also what a `needs:`-dependent job shows when an UPSTREAM job in the SAME workflow
failed** — `ci-images`, `scanner-images` and `linux` read `skipping` because the `guard` step ahead of them
failed, not because the diff deselected them. So a rollup like `1 guard fail / 3 skipping / 1 ci-verdict
fail` is ONE defect (the guard's failing step) plus its cascade: never count the skipped rows as extra
scope and never report "N gates blocked" — read the guard job's failing STEP name and route that one.

Corollary: `mergeable_state: unknown` is GitHub *recomputing*, not a hold — it persists for minutes after
a freshly-updated PR. A PR with an all-SUCCESS rollup and `unknown` state is
merge-ready pending recompute; do not translate it into `BLOCKED` and do not hunt for a pending run that
does not exist. Read `mergeable` (true/false/null) alongside it, and if you need the blocking reason,
`mergeStateStatus: BLOCKED` plus `reviewDecision: REVIEW_REQUIRED` is the actionable pair.

## `BLOCKED` + `REVIEW_REQUIRED` is NOT proof of an owner gate — probe eligibility and split the rollup FIRST

Reporting a PR as "blocked on owner approval" is a claim, and it is the single most common way a planner
mis-parks a real, bot-fixable red in the human bucket while a lane sits idle. Before that word escapes,
do two measurements.

**1. Split the rollup: an approval requirement and a red required CHECK both set `mergeable_state: blocked`.**
The pull API's `review_decision` is the review-gate fact; `mergeable_state: blocked` with
`review_decision: null` means nothing is requiring a review — a *failing required check* is blocking. That
red (a build/serve leg, a lint gate, an acceptance gate) is bot work, not an owner gate:

```bash
gh api repos/<o>/<r>/pulls/<n> --jq '{state:.mergeable_state, review_decision, mergeable}'   # review_decision null => not a review gate
sha=$(gh api repos/<o>/<r>/pulls/<n> --jq .head.sha)
gh api "repos/<o>/<r>/commits/$sha/check-runs?per_page=100" \
  --jq '(.check_runs // .)[]|select(.status=="completed" and .conclusion=="failure")|.name'   # the real reds to route
```

Classify each red into exactly one bucket: (a) bot-fixable build/serve/lint → owning lane; (b) verdict-gated
write-back (a reviewer's `acceptance_writeback` ticks the criteria) → reviewer/`#1644`; (c) a genuine
review requirement → below.

**2. Probe whether the only available identity can even submit an approving review — GitHub refuses
self-approval by rule.** Every lane typically authenticates as the PR *author's* account, so a POST
`APPROVE` from that token returns `422 Can not approve your own pull request`. That 422 is the mechanical
proof the item is owner-gated (only a non-author identity clears it), and it is worth running once rather
than asserting from memory:

```bash
gh api repos/<o>/<r>/pulls/<n>/reviews -f event=APPROVE -f body='eligibility probe' 2>&1 | head -3

# 422 Can not approve your own pull request  => genuinely owner-gated; no bot can carry it
```

A 200/`state: APPROVED` means the identity CAN approve (it is not the author) — approve and move on; never
tell the owner a PR "needs your click" when the fleet's own token would satisfy the gate. Never leave the
probe as a real review on someone else's PR: if it succeeds, that IS the approval you wanted to delegate; if
it 422s, nothing was recorded.

**Do not read an admin-404 as "no gate."** A token with `push` but not `admin` gets `HTTP 404` from
`/branches/main/protection` and `/rulesets/<id>` may show only `deletion`/`non_fast_forward` while the
required-review config lives in repo settings the token cannot see. A 404 on branch protection from a
non-admin token is a permission gap, not evidence the review rule is absent — trust the PR's own
`reviewDecision`/`mergeable_state` over the settings endpoint.

**Report line when it IS owner-gated:** name it "owner-approval gate — GitHub rejects self-approve (422),
only a non-author identity clears it", and state what the *bots* already did (evidence comments posted,
build reds routed to their lanes) so "waiting on owner" is visibly one narrow step, not a stalled board.
Then still find the idle-capable lane work that is NOT behind this gate and dispatch it — an approval gate
on five PRs is never a reason for zero dispatches this pass.

## A reviewer verdict / head-scoped report is a claim about the HEAD it quotes, not the branch

Same rule, opposite subject: a reviewer's verdict quotes a head sha just as a lane's report does, and
a lane's scrub/fix push races the reviewer. The verdict routinely lands seconds AFTER the head it was
measured at has been superseded — so "NOT green at `<old>`: gate X reds" can describe a head that no
longer exists while gate X is already green at the new head. Before repeating or dispatching off any
head-scoped verdict, compare the sha it cites against the CURRENT head:

```bash
gh pr view <n> --json headRefOid --jq .headRefOid    # compare with the sha the verdict quotes
```

If they differ, re-measure the cited gate at the current head **by STEP, not by check name** — the
red moves between steps across heads (a `check-pr-closing` red at the old head becomes a by-design
`check-pr-acceptance` red once the scrub lands):

```bash
gh api repos/<o>/<r>/actions/jobs/<JOBID> --jq '.steps[]|{n:.number,name,c:.conclusion}'
```

Then: (a) the cited gate cleared → record the reconciliation on the PR and ask the reviewer to re-anchor
its verdict at the new sha; never re-dispatch a defect the stale head already fixed; or (b) the SAME gate
still reds at the new head → the verdict is current, only the sha label was stale, and the owed work
stands. Do not assume either direction — the head comparison plus a step-level re-measure settles it, and
the step conclusion at the current head (with its job id) is the evidence to post.

## A `guard`/acceptance red measured BEFORE an AC write-back is STALE — a re-run clears it

`check-pr-acceptance` (the `guard` job) reds on a PR whose linked issue still has unticked `- [ ]`
criteria. When a reviewer's verdict lands and writes the ACs back (ticks `- [ ]` → `- [x]` with
`proven:` evidence lines), the guard red that ran *before* that write-back now describes a state that
no longer exists. Compare the check's own timestamps to the write-back's `created_at`:

```bash
gh api repos/<o>/<r>/commits/<head>/check-runs \
  --jq '.check_runs[]|select(.name=="guard")|"started="+(.started_at//"")+" completed="+(.completed_at//"")+" c="+(.conclusion//"")'
gh api repos/<o>/<r>/issues/<issue>/comments --jq '.[-1]|.created_at'   # the AC-tick time
```

If the guard's `completed_at` is BEFORE the tick's `created_at`, the red is stale: it failed on the
then-unticked ACs, the ACs are now `[x]`, so a guard **re-run** goes green with no tree change. Tell the
lane "guard red is stale (ran <t1>, ACs ticked <t2>) — re-run clears it; do not route it as a defect or
weigh it against the PR"; a still-red re-run is the real finding to route. The timestamp ordering is the
tell — a genuine content defect does not clear on a re-run of the same tree.

**Settle "stale or real?" yourself by running the gate binary at the head — do not queue a CI round-trip to
find out.** The body-reading gates are plain scripts over a body file, so a throwaway worktree at the head
executes exactly the code CI executes:

```bash
WT=<scratch>/wt-verify; git worktree add --detach "$WT" <head-sha>
cd "$WT" && gh pr view <n> --repo <o>/<r> --json body --jq .body > /tmp/body.md
python3 scripts/check_pr_acceptance.py check --body-file /tmp/body.md; echo rc=$?
git worktree remove --force "$WT"       # remove only YOUR probe; never prune anyone else's worktree
```

`rc=0` plus the gate's own OK line ("every closed issue's `## Acceptance criteria` is checked or named out of
scope") PROVES the red is stale-by-construction and the PR is green on merit; a still-failing local run names
the exact criterion to route, so the fix-dispatch carries the real defect instead of "go look". Post the
command, its output line and the rc on the PR — that converts an ambiguous "wait for the re-run" into a
measured fact at zero CI cost, and it is read-only: nothing pushed, no run cancelled, no gate re-judged. Leave
the actual re-run to the owning lane or to the next legitimate push. Do not skip this because the red looks
obvious: the same technique settles any body/tree-reading gate (hygiene, closing, agents-line) in one call.

**The stale red is not only about the tick — it is about the body CONTENT the gate read.** `check-pr-acceptance`
also reds when a criterion IS `- [x]` but its `(proven: …)` names no replayable run id and no reproducible
`command + rc=… + sha`. So a lane can fix such a red by **editing the body** (adding `proven:` evidence) with
NO commit — head unchanged — and the failing check-run still describes the pre-edit body. Compare the guard's
`completed_at` against the body edit time (`gh api repos/<o>/<r>/issues/<n> --jq .updated_at`, or the write-back
`comment.created_at`), not only against a `- [ ]`→`- [x]` tick: a body edit AFTER the guard's `completed_at`
leaves the same stale-by-construction red, cleared only by a fresh run at that head.

**Two `guard` rows can sit at ONE head** — a re-run/rerun-failed-jobs produces a second check-run beside the
first, so `commits/<sha>/check-runs` may list `guard: failure` (older) AND `guard: success` (newer) together.
The union is not a contradiction: read each row's `started_at`/`id` and trust the NEWEST completed one. Before
routing "guard still red", list every guard row with its timestamp; a failure that predates a fresh success at
the same sha is a stale duplicate attempt, not a live defect. Same rule as the `status=="completed"` discriminator
above — a name match is not a verdict.

## A rebase never clears a `check-pr-acceptance` red — the same unchecked criterion at every head is PRE-EXISTING, not a regression

When a head is rebased or re-pushed onto a newer `origin/main` and the guard still reds on the SAME step —
`make check-pr-acceptance`, same quote (`… acceptance item N ("…") is still `- [ ]` in the linked issue's

## Acceptance criteria, yet the PR body closes the issue`) — the rebase did not break anything: the
criterion is genuinely unticked and `closes #N` proves only that the body names the issue. Compare the
failing **STEP name** across the old and new head (never the check name — it is `guard` on both heads, so
by name the red "persists" even when the step changed); an identical step + identical criterion is proof
of pre-existing. Say it explicitly — "this red is pre-existing at `<old-head>` and `<new-head>`; the rebase
introduced no regression" — so the lane does not burn a third rebase. The only two remedies are: prove the
criterion and tick it via `acceptance_writeback` (reviewer-gated, #1644), or move it under `## Not covered`
with a linked work item. A rebase is never the fix for an acceptance red.

## A `workflow_dispatch`-only workflow's reds are STALE until re-dispatched at the post-fix sha

A matrix that only runs on manual dispatch (engine-build, ci-images) does not re-run when a fix merges to
`main`. So the newest run's reds describe the sha it was dispatched at, **not** current `main`. Before you
classify a cell as a live defect, compare the run's `headSha` to the merge sha of the fix that was supposed
to address it:

```bash
gh run list --workflow <id> --limit 1 --json databaseId,headSha,status   # is headSha BEFORE the fix merge?
gh api repos/<o>/<r>/commits/main --jq .sha                              # current tip
```

If the run predates the fix, the honest statement is "these reds are stale, re-prove needed" — not "these
cells are broken". Dispatch a fresh verify sweep at `ref=main` (see `references/pipeline-verify-matrix.md`
§5 for the dispatch quirks) and classify against **that** run's head, not the old one.

## A main-tip `check-pr-base` red with `foreign commits (0)` is PHANTOM when main advanced mid-run

`check-pr-base` — and any gate that compares the run's HEAD to a freshly-fetched `origin/main` — reds on a
**push-to-main** run whenever main advances between the run's HEAD and the gate's `git fetch origin main`.
The push run's HEAD is the merge commit; the fetch pulls the newer tip; so `merge-base(origin/main, HEAD)`
equals the merge commit, not `origin/main`, and the gate reports "not cut from origin/main" with
`foreign commits (0)`. Nothing foreign is carried — the red is a measurement artifact. The workflow step's
own comment ("a push to main has origin/main == HEAD, so the gate is a tautology") is FALSE whenever main
moves mid-run, which in a busy fleet is most runs. It is the `check-pr-base` sibling of the `ci-verdict`
main-tip class above: same root shape (a main-tip run measured against a moving main), different gate.

Distinguish it from a REAL base-staleness (a branch cut from another PR): the real one carries
`foreign commits > 0` and its merge-base is an older, unrelated commit. The phantom has zero foreign commits
and the run's HEAD IS an ancestor of current main:

```bash
git merge-base --is-ancestor <run-head-sha> <current-main-tip> && echo 'on main (phantom red)'
gh api repos/<o>/<r>/actions/runs/<run-id> --jq '{head:.head_sha[0:8],event,conclusion}'  # event=push?
```

**Post-merge verification must use ANCESTRY + all-real-gates-green, never a green main-tip run.** "Main is
green at the merge tip" is structurally unachievable while main advances faster than a CI run completes, so
do not hold a merged-PR acceptance-criteria row open waiting for it — cite `git merge-base --is-ancestor
<merged-sha> <current-main>` = YES plus the pass list of the real gates (authors, closing, hygiene,
acceptance), and name the `check-pr-base` red as the tracked phantom. File the gate fix as its own issue
(make the step event-aware: skip on push, or compare `github.event.before` instead of a re-fetched
`origin/main`) — then main-tip runs go green and the manual characterization ends.

## Read a `ci-verdict` red from the check-run's `output.summary` FIRST — one call gives subject + failing job

A failed `ci-verdict` check-run's own `output.summary` embeds the whole judged-run header and the per-job
scope tally, so you do not need the job log to learn which job broke or which PR it belongs to:

```bash
gh pr checks <n> --repo <o>/<r>        # the ci-verdict row's numeric column is the CHECK-RUN id
gh api repos/<o>/<r>/check-runs/<check-run-id> --jq '.output.summary'

# -> "[ci-verdict] run 42304990756 CI head=673ee85 event=pull_request branch=agent/... conclusion=failure

#     [ci-scope] guard success / [ci-scope] scanner-images FAILED / [ci-scope] linux/unit success ...

#     [ci-scope] summary: verdict=red success=9 failure=1 ..."
```

This is strictly cheaper than resolving the wrapper→judged run from the log, and it names the failing JOB
outright (`FAILED` suffix). Then pull only that job's log for the failing step. The wrapper's own
`head_sha`/`output.title` remain unreliable for subject resolution (see the WRAPPER section above); the
summary line's `run <id> ... event=<x> branch=<y>` is the authoritative subject.

## `gh run view --json jobs` yields `id: null` — take job ids from `databaseId` or the `/jobs` API

`gh run view <run-id> --json jobs --jq '.jobs[].id'` prints `null` for every row; the jobs payload keys the
job id as **`databaseId`**. A null id then makes `actions/jobs/<id>/logs` 404. Use either:

```bash
gh api repos/<o>/<r>/actions/runs/<run-id>/jobs --jq '.jobs[]|select(.name=="<job>")|.id'
gh run view <run-id> --json jobs --jq '.jobs[]|{databaseId,name,conclusion}'
```

## A job with no workflow file of its own (`gh run list --workflow <name>.yml` → 404) is a matrix job in a composite workflow

`scanner-images`, `ci-images`, `linux/*` are matrix legs inside a composite CI workflow, not standalone
workflows — so `gh run list --workflow scanner-images.yml` returns `HTTP 404: workflow ... not found` and
`commits/<sha>/check-runs` may hold no row of that name at main. Do not conclude the job does not exist:
find it in its parent run's `/jobs` list (`gh api repos/<o>/<r>/actions/runs/<run-id>/jobs`) and read it
by that job id. Same for `--json jobs` naming: the leg name is the row's `name`.

## Before routing a red to a PR lane, test INDEPENDENCE with `gh pr diff --name-only`

A red job is only the PR's defect if the PR could have caused it. Diff the PR's files once and compare
them to what the failing job builds — a scanner-container build failing while the diff is
`ci-verdict.yml`+`openspec/`+`CHANGES` is an independent/pre-existing failure that belongs to the owning
lane (security builds scanners), not a regression for the PR author to chase:

```bash
gh pr diff <n> --repo <o>/<r> --name-only
```

Say so explicitly in both dispatches — to the PR lane ("not a regression: your diff touches none of these
inputs; do not chase it") and to the owning lane ("build failure at <run>/<job>/<step>, blocks #N's
ci-verdict; file tagged or route a retry"). Routing an independent red to the PR author burns a whole run
on a defect its branch cannot fix, and the PR stays red while the real owner never hears about it.

## `replace_all` note

The `ci-verdict` check-run with `conclusion: failure` and an empty `output.title` remains common for reds;
`output.summary` is populated even when the title is not, so `.output.summary` is the field to read, not
the title.

## Classify each matrix red into exactly one bucket before filing anything

A 10-plus-cell run mixes three causes; reporting them as one "engine is broken" is wrong and files noise:

| Bucket | Tell | Action |
|---|---|---|
| **Stale / pre-fix** | run head sha is before the fix's merge sha | re-prove with a fresh dispatch; do not file |
| **Infra** | `no space left on device`, runner killed / `exit 143` / shutdown signal, log-artifact `404` | build-host backpressure, not a code defect; retry-dependent, do not file as a code bug |
| **Genuine serve-cell** | a declared serve cell (engine×arch present in `data/engine-capabilities.json`) fails its own build/install/serve leg with a real error (missing module, serve timeout, flag no-answer) | real defect — file/route to the owning lane and **fix it; never de-scope a declared serve cell** |

Before filing any cell, search open issues for the engine/arch and the exact error symbol (`poetry`,
`TimeoutError`, etc.) — the defect is often already tracked on a monitor issue, and the right action is a
comment on that tracker, not a new issue.

## `<!-- auto-merge: deferred <sha> -->` is the gate working

The arming bot writes that comment when the head still has a non-completed run — a mid-flight head is
not verified, so it is not merged. That is correct, not a lane jumping the queue. Confirm the truth
from the field, not the comment:

```bash
gh api repos/<o>/<r>/pulls/<n> --jq .auto_merge      # null = nothing armed
```

**The deferral names ONE blocking reason; the head can carry a DIFFERENT actionable red. Enumerate every
concluded non-success row and classify each, never route only the cited one.** A deferral reading
"still has a red check `ci-verdict`" is a single row picked from the rollup — the same head routinely fails
`scope` and `guard` on a separate, real gate step (measured: both red on `make check-pr-acceptance` while
the deferral cited only `ci-verdict`). Routing the cited name alone sends the lane after the tracked
catch-all and leaves the real defect untouched. So on every deferral:

```bash
sha=$(gh api repos/<o>/<r>/pulls/<n> --jq .head.sha)
gh api "repos/<o>/<r>/commits/$sha/check-runs?per_page=100" \
  --jq '(.check_runs // .)[]|select(.status=="completed" and .conclusion=="failure")|.name'
```

Then pull each failing job's failing STEP (`--jq '.steps[]|select(.conclusion=="failure")|.name'`) — the step
name, not the check name, assigns the bucket. A `ci-verdict` row is downstream of whatever actually broke; a
`scope`+`guard` pair failing the SAME real step is ONE defect (see `pr-closing-gate.md` for the
`check-pr-acceptance` / `check-pr-closing` remedies), while `scope`+`guard` failing on *different* steps, or
beside a null-conclusion row, is the cascade or mid-flight case. Never report two causes when one step name
covers both rows, and never let a deferral's single cited reason stand in for the rollup.

GraphQL `AutoMergeRequest` has **no** `commitHead` field — requesting it returns `undefinedField`.
Read the head from the PR object instead.

## `ci-verdict: NO DECISION — this run published no scope decision` is downstream

A scope / `check-pr-agents-line` failure kills the run before it publishes a scope decision, so the
verdict job then reds on the same root. Trace it to the first failing gate; never file the verdict red
as an independent defect (it will be deduped at best, and it buries the real root at worst).

## A `ci-verdict` red's `head_sha` is the WRAPPER's branch, not the run it judged — resolve the judged RUN_ID

`ci-verdict` runs on `event=workflow_run`, so it is a wrapper: it fires on some other run's completion and
then judges THAT run. The wrapper's own `head_sha`/`head_branch` is the branch the wrapper itself ran on
(frequently `main`, because the wrapper workflow file lives there), which is NOT the subject of its verdict.
Reading `commits/<main-sha>/check-runs` and seeing `ci-verdict: failure` therefore does NOT mean "main had a
red at that head" — it means the wrapper that happens to run on main judged some run and failed it. Filing
"post-merge main-red at <main-sha>" off the wrapper's head is a misdiagnosis that sends the owning lane
chasing a phantom, and it is a claim you will have to retract.

Resolve the SUBJECT before classifying: read the judged run id the wrapper logged, then look up that run's
own event/head/branch:

```bash
gh run view <wrapper-run-id> --log | grep -oE '\[ci-verdict\] run [0-9]+|--run-id "?[0-9]+' | grep -oE '[0-9]+' | head -1
gh api repos/<o>/<r>/actions/runs/<judged-run-id> --jq '{head:.head_sha[0:8],branch:.head_branch,event,conclusion}'
```

The judged id is NOT logged as a bare `RUN_ID: NNN`. Match the two forms the workflow actually
emits: the argv line `python3 scripts/ci_verdict.py … --run-id "42239878499" …` and the summary
line `[ci-verdict] run 42239878499 CI head=…`. A `grep 'RUN_ID: [0-9]+'` returns EMPTY, so you
conclude "no judged run" and mis-file the wrapper red against `main` — the exact false main-red
this section exists to prevent. The job's own log
(`gh api repos/<o>/<r>/actions/jobs/<job-id>/logs`) prints the same `[ci-verdict] run <id>` summary
plus a per-job scope tally (`linux/unit FAILED`, `pull_requests:[#N]`) — the fastest subject read.

If `event=pull_request`, the verdict is holding that PR's run — its red belongs to the PR (and is often a
defect already tracked on it), NOT to main. A wrapper whose judged run is a `pull_request` event at a fork/PR
head proves nothing about `main`'s health. Only when the judged run is itself a `push`/`schedule` run on the
`main` head is a `ci-verdict` failure a genuine main-red. A mixed `check-runs` tally at one commit (many
`verdict` rows, some success some failure) is the aggregate of many wrappers each holding a DIFFERENT run —
it is not a clean "main is red". Retract your own already-posted main-red route the moment the judged RUN_ID
shows a PR run; name the retraction comment id and cite the wrapper→judged-run mapping as the evidence.

## A `ci-verdict` wrapper red whose judged run is EXPIRED (`no ci-scope-decision artifact`) is a re-judge artifact, NOT a post-merge regression

After a ci-verdict judge fix merges, the merged commit accumulates MANY `judge`/`verdict` check-runs at one
head — one per `workflow_run` firing. Several can be `failure` **simultaneously with** a `success`, and the
tip looks red when it is green. The tell is the failure's own log line:

```
[ci-verdict] run <old-id> published no ci-scope-decision artifact.
[ci-verdict] FAILED: run <old-id> has no verdict
```

That is a re-judge of an OLD run whose job records have **expired** (GitHub purges `jobs?per_page=100` →
`total_count=0` and the artifact after ~90 days / on pruning). "No decision artifact" is the correct verdict
for a vanished run — it says nothing about the current tree. Distinguish decisively: read the CI run the
wrapper JUDGED (subject resolution above); if its id is much older than the merge and its jobs are gone, the
red is an artifact.

**A `judge`/`ci-verdict` failure on `main` right after a merge is classed as KNOWN-artifact FIRST, not reflexively filed as "main red at the merge" — check whether its fix PR is still OPEN.** The wrapper fires on every run completion, so the first moments after ANY merge show a fresh `judge: failure` row at the merge tip; before you file a new main-red issue naming the merged PR, spend one call resolving the class: if the failure log says a run published no `ci-scope-decision` (an upstream scope gate skipped it) AND the issue/PR that tracks that defect is still open, it is the tracked artifact, not a regression the merge introduced. Only a `judge`/`verdict` red whose judged run is a live `push` CI run at the merge tip AND whose defect has no open fix belongs on a new issue. Stating the class (with the fix-PR number and its open state) is the honest merge-verify verdict; a bare "main is red after #N merged" is a misdiagnosis you will have to retract.

**The decisive verdict is the NEWEST wrapper judging the NEWEST CI run — match by the check-run `output.title`.**
The green verdict carries its subject in the title text: `ci-verdict: green (run <id>)`. Equate that `<id>` to
the post-merge push run at the merge tip; that check-run's `conclusion` is the real main-health fact:

```bash
gh api repos/<o>/<r>/commits/<merge-sha>/check-runs \
  --jq '.check_runs[]|select(.name=="ci-verdict" or .name=="judge")|{id,name,conclusion,title:.output.title}' | grep -i "run <post-merge-id>"
```

Do not let a batch of expired-run `failure` rows at the tip override the one `success` row whose title cites
the live post-merge run. Report main-health off the subject-matched green, name the expired-run rows as
tracked artifacts (not regressions), and never ask a lane to "fix main" over them.

## A familiar red beside a NEW one makes the whole head read as noise — classify every concluded failure row

A head routinely carries a red you have already classified (a `ci-verdict` wrapper judging a cancelled run, a stale
`guard` acceptance row) *together with* an unclassified genuine defect. Naming the head "the known class" after
recognising the familiar row is how a real defect survives a whole sweep cycle. Enumerate every concluded failure at
the head and give each its own verdict before you summarise:

```bash
gh api repos/<o>/<r>/commits/<sha>/check-runs?per_page=100 \
  --jq '(.check_runs // .)[]|select(.status=="completed" and .conclusion=="failure")|.name'
```

Each name resolves to its own job → failing STEP → log line. The deliverable is one row per red with
{name, run/job id, failing step, class, owner}, where `known-confounded` is only written after the log confirms it —
never because the name matches a class seen before. A sweep that reports "only the tracked ci-verdict red" while a
`engine-build-*` cell or a `linux/unit` step is also `completed/failure` has mis-reported the board.

## A fleet-splice `ci-unit` red ("the rule source is older than this SOUL") is a DEFECT with a two-file fix

`test_the_fleet_splice_is_idempotent_and_refuses_an_older_source` fails with

```
REFUSING: the rule source is older than this SOUL — it would drop 1 rule(s):
  - **<the rule the diff adds>**
Source: agents/<lane>/skills/<skill>/references/standing-rules.md
Update references/standing-rules.md, or pass --force if the removal is intended.
```

when a PR adds a rule to the fleet rule source (`agents/standing-rules.md`) but not to every per-lane copy under
`agents/*/skills/*/references/standing-rules.md`. The splice refuses rather than silently dropping a rule, so the
red is CORRECT and the fix is a second file in the SAME diff: update each per-lane `references/standing-rules.md`
the log names so the source is >= every live SOUL. Never `--force`, never a rebase, never a test edit. Route it to
the docs lane (reference files are its surface) quoting the exact path and the dropped rule line from the log.

## One monitor tracker per RUN — append every red cell, never one issue per red

When a long matrix run (engine-build, ci-images, any per-cell fan-out) reddens several cells, the whole
run gets **one** tracker issue: open it once the owner or a lane asks to monitor the run, and **append a
comment per red cell** as each concludes — cell name + job id + the quoted first-diverging line + a
classification (build / install-leg / serve-leg / host-verify / skip-not-honored / infra). Do not open a
fresh issue for each cell: it fragments the trail, duplicates the investigation, and every future reader
has to re-derive that the cells belong to one run and one dispatch. The tracker's body carries the run id,
head sha and the acceptance criteria (monitor to conclusion; diff failing vs succeeding cells; per-cell
verdict; next action); each comment is a measured data point at a dated sha.

Cells that already concluded `failure` inside a still-`in_progress` run are diagnosable immediately —
select them from the run's `/jobs` list by `conclusion=="failure"`, pull each job's own log, and record it
on the same tracker without waiting for siblings to settle. This is the same one-vehicle principle as
one-PR-per-issue, applied to run monitoring.

## A lane's mid-flight matrix progress report is a snapshot — re-measure the run before classifying

A lane reporting a long matrix sweep mid-flight ("N/M concluded, 0 reds, K cells still building") describes
the moment it polled, not the run's current state. The run advances past the poll, so both the red count and
the "still building" set are stale: a cell the lane names as still building has frequently ALREADY concluded
**failure**, and its "0 reds" is an artifact of sampling before that cell settled. Never repeat the lane's
tally as fact, and never accept "the rest are building, we'll see" as a reason to wait — a concluded red
inside a still-`in_progress` run is diagnosable now.

Re-measure the run's own `/jobs` and tally by status/conclusion:

```bash
gh api repos/<o>/<r>/actions/runs/<run-id>/jobs?per_page=100 \
  --jq '[.jobs[]|.status+"/"+(.conclusion//"-")]|group_by(.)|map({(.[0]):length})|add'
gh api repos/<o>/<r>/actions/runs/<run-id>/jobs?per_page=100 \
  --jq '.jobs[]|select(.conclusion=="failure")|{name,id:.id}'
```

Then classify each `completed/failure` cell immediately (bucket table above) — do not wait for siblings. Read
the failing STEP names before deciding the bucket: a red on the **build step** (`make build-engine` / a
`uv`/`pip install` step, e.g. a missing build-backend module) is a genuine content red in that cell's
committed params, distinct from serve/host legs reading `completed/skipped` (AC-3-skippable runner-absence).
`skipped` serve/host legs beside a red build step is a build defect, NOT an env skip — do not let the lane
call it a skip. Tell the lane its snapshot was stale, hand it the concluded red with the job id and quoted
first-diverging line, and require the six-section issue (or an explicit AC-3 judgment recorded on-thread) —
never let "0 reds / still building" stand as the conclusive AC verdict.

## Filing a gap: `gh issue create` with mixed `-f` and `--input` fails

Split it into two calls — create with `-F title=` and the body from a file, then PATCH the labels:

```bash
gh issue create -t '<title>' -F body=@/tmp/body.md
gh api -X PATCH repos/<o>/<r>/issues/<n> --input /tmp/labels.json   # {"labels":[...]}
gh api repos/<o>/<r>/issues/<n> --jq '{n:.number,labels:[.labels[].name]}'   # read back
```

Always read the labels back; the PATCH exit code is not the fact.

## A stale base masquerades as an unrelated gate red — `mergeStateStatus: BLOCKED` never says `BEHIND`

When several open PRs simultaneously show a *different-looking* red (one `ci-verdict`, one `guard`, one
`linux/unit`, one `scope`), suspect ONE shared cause before classifying them individually. GitHub reports
`mergeStateStatus: BLOCKED` — **never `BEHIND`** — as soon as any check is red or a review is pending, so a
branch that has merely drifted behind `main` reads as whatever gate happens to fail on it. The base
staleness is masked and the visible reds are cascade.

Test the whole board in one pass instead of per-PR triage:

```bash
MAIN=$(git rev-parse origin/main)
for n in <prs>; do
  h=$(gh pr view $n --json headRefOid --jq .headRefOid)
  git merge-base --is-ancestor "$MAIN" "$h" && echo "#$n current" || echo "#$n STALE"
done
```

If the heads are uniformly stale while `mergeStateStatus` is uniformly `BLOCKED`, the reds are not defects:
`check-pr-base` ("HEAD is NOT cut from origin/main") reds `linux/unit`, which reds the run, which makes
`ci-verdict` red, which makes the state `BLOCKED`. **One rebase clears the whole set** — do not dispatch a
fix per gate name. Verify the diagnosis by reading the failing STEP of one PR: a stale base shows
`check-pr-base` while every other gate in that job never evaluates.

Corollary for automation: a sweep that classifies on `mergeStateStatus` alone (`BEHIND`/`DIRTY`) will pass
over every stale-and-red PR forever, reporting `success` with `rebased: 0`. That is a code defect for the
code lane — the unblock is still a host-lane rebase, not a wait.

## A rebase that turns `guard` green usually EXPOSES a content defect — read the failing `make` target

`check-pr-base`/`guard` green proves base freshness, not that the PR's own diff is clean. After a rebase
fixes the base gate, the remaining red in the same `linux / unit` job is normally a *content* defect the
stale base was masking, and it is almost never the unit tests. Read the job log for the
`make: *** [Makefile:<n>: <target>] Error` line before naming any cause:

- `check-<x>-gate` / `check-pr-<x>` targets are **static lint over the tree** (script call sites, body
  hygiene, author allowlists) — they run before/around pytest and red the job on their own. A red there
  is a one-line source fix, never "the branch is stale".
- Only a `pytest`/`go test` failure block is a test red.

Consequence for dispatch: a lint-gate red is **not** a rebase or re-run. Say so explicitly to the lane —
"do not rebase again and do not re-run CI; the base is correct (`compare(main→head)` behind 0), only the
source line is wrong" — otherwise the lane re-runs a matrix to reproduce a deterministic static check.

**Escape-hatch comments are matched by LINE-BASED regexes, so a tag on the continuation line is invisible.**
A gate that allows a construct only when tagged (`# proc-allow: <reason>` on a bare `subprocess.*` site,
`# noqa`, `# type: ignore`, `# nosec`) matches the line holding the CALL, not the logical statement. A
multi-line call whose tag sits on the wrapped second line reads as untagged and reds. Diagnosis recipe,
which produced an exact one-line remedy rather than a guess:

```bash
git show <head>:scripts/<gate>.py | grep -n 'RE = re.compile'   # the CALL_RE and ALLOW_RE patterns
```

The gate's own docstring/comment states the matching rule (e.g. "a trailing `# proc-allow:` on the same
line") — quote it in the comment you post, plus the two regex line numbers, so the remedy is unimpeachable:
move the existing tag to the end of the line that carries the call. Same reason text, no behaviour change.

## At a main merge tip, classify each run by `event`+`name` — only the `push`-event `CI` run is main's health

`actions/runs?branch=main` at a fresh merge sha lists several runs, and two of them are traps:

| `event` + `name` | What it is | Main-health fact? |
|---|---|---|
| `workflow_run` `ci-verdict` (also `auto-merge`) | a wrapper that fires on SOME other run's completion and judges THAT run | **No** — its failure is the judged run's red (often a PR's), and its success is not a matrix pass |
| `push` `CI` / `ci-hf-live` | the run GitHub fires on the merge itself | **Yes** — this is the only main-health run |
| `push` `registry-liveness` | bookkeeping | No |

So on a merge-verify pass, a `failure` row among the `workflow_run` wrappers is **not** "main is red" —
resolve each wrapper's judged `--run-id` (see the WRAPPER section above); in practice they judge the PR runs
that just completed, whose red is expected and belongs to those PRs. Equally, an `auto-merge` `success` at
the main sha is not a green — it is the arming bot running, not the matrix. The honest merge-verify statement
is scoped to the `push`-event `CI` run's own conclusion, and if that run is still `in_progress` (it commonly
starts ~2 s after the merge and runs for many minutes), the correct verdict is **main not yet proven**, which
is neither "green" nor "red". Never upgrade an `auto-merge` success or a wrapper's failure into either one.

```bash
gh api "repos/<o>/<r>/actions/runs?branch=main&per_page=15" \
  --jq '.workflow_runs[]|"\(.id) [\(.event)] \(.conclusion//\"-\")/\(.status) head=\(.head_sha[0:10]) \(.name[0:34])"'

# main-health = the row with event==push and name==CI (or the push ci-hf-live), nothing else
```

Multiple `ci-verdict` wrappers each `failure` minutes apart at one main head are exactly this shape: one
wrapper per PR run that concluded, each holding its own PR's red — not a growing main regression. Count them
as distinct subjects, not as accumulating main reds.

A `judge`/`ci-verdict` FAILURE row frequently carries an EMPTY `output.title`/`output.text`/`output.summary` —
only a GREEN verdict tends to put `ci-verdict: green (run <id>)` in the title, so do not expect the failed
wrapper to name its subject in the check-run output. Resolve each red wrapper's judged run from its own run
log (`gh run view <wrapper-run-id> --log | grep -oE '\[ci-verdict\] run [0-9]+|--run-id "?[0-9]+'`), then look
up that judged run's `event`/`head_branch`: a `pull_request` subject means the red belongs to that PR, not to
main. When the log is unavailable, `actions/runs/<wrapper-id>` plus the judged run's completion time still
identifies the subject.

A merge tip's `commits/<sha>/check-runs` list also contains the tip's `engine-build-*` matrix cells as
`status=queued|in_progress, conclusion=null`. Those are the matrix not yet reconciled, NOT main reds — counting
them as "still red" is the null-conclusion trap at the merge tip. While the matrix (or the post-merge `push`
CI run) is still settling, the honest verdict is "core CI green at the tip, full-tip matrix pending" — never
"main green" and never "main red". Take main-health from the `push`-event `CI` run's own `conclusion` plus a
subject-matched green `judge` row; do not hold a merge open on the engine matrix, whose green-at-tip is
structurally unachievable while main advances faster than the matrix completes.
