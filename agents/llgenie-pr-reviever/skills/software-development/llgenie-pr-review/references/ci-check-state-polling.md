# Reading CI state at a head sha — one source, one poll

Related depth, linked from SKILL.md's body-gate section: `writeback-subset-citation-traps.md` (the
acceptance write-back's subset-wipe / `#<n>`-citation / paren-ref traps and the circular-CI-criterion
rule), `agents-line-aborts-acceptance-verdict.md` (an early hygiene gate that aborts the chain leaves
the heavy rows SKIPPED, so no completion verdict is possible), `agent-profile-tree-review.md`
(read-only tree↔live drift measurement; COPY/fold destroys tree-only lines).

The verdict is a claim about a sha, so the only trustworthy read is the full check-run set *at that sha*. Getting that read wrong is the single most reliable way to burn twenty tool calls and still quote a wrong verdict.

## The one authoritative command

```
gh api repos/<owner>/<repo>/commits/<sha>/check-runs > /tmp/cr.json
python3 - <<'PY'
import json
d = json.load(open('/tmp/cr.json'))
print('total_count =', d.get('total_count'))
for cr in d.get('check_runs', []):
    print('%-7s / %-9s %-30s %s' % (cr['status'], cr.get('conclusion'), cr['name'], cr['id']))
PY
```

- Cache to a file, then print in **one** interpreted step. Piping the JSON through `grep -E '"name"|"status"'` surfaces the nested `app` block's own `"status"`/`"name"` keys and makes the output unreadable.
- The set legitimately contains **several check-runs with the same name** (`guard` appears once per workflow that calls the shared gate). A duplicate name is neither a duplicate run nor an anomaly — never dedupe it and never report it as a problem.
- `total_count` is the assertion. If your enumerated lines disagree with it, you have a parse problem, not a shorter check list.

## `gh pr view --json statusCheckRollup` vs the REST payload

`statusCheckRollup` exists only on the GraphQL-backed `gh pr view --json ...`. `gh api repos/<R>/pulls/<n>` returns REST, which has no such key — a `KeyError: 'statusCheckRollup'` there means *wrong endpoint*, not *no checks*. Use `gh pr view <n> --json statusCheckRollup` for the rollup shape (states come back as `SUCCESS`/`IN_PROGRESS`/`FAILURE`), and the check-runs endpoint when you need per-run ids for a log fetch.

## `gh pr checks` exit 8 is a state, not a failure

`gh pr checks <n>` exits **8** whenever any check is pending or failing. That is the normal answer while a run is in flight — not a broken command, and re-running it with different flags will not produce a 0. It prints a tab-separated table (`name<TAB>pass|fail|pending<TAB>seconds<TAB>url`); the exit code is the only signal worth reading from it.

## Escaping traps belong to the shell, not the tool

- `grep -P '\tfail\t'` inside **double** quotes passes a literal backslash-t; grep answers `warning: stray \ before t` and matches nothing, so a poll reports `fail=0` forever. Use `awk -F'\t' '$2=="fail"'` on captured text, or `--json name,state` filtered in python.
- `$?` after `cmd | head` is `head`'s status. Capture to a variable or file before asserting on a piped command.
- `sleep45` (no space) is a command lookup, not a delay: every retry fails identically and the loop log shows stale data.

## Poll the run, not the checks

While work is in flight, poll **one** bounded background job on the *workflow run id*:

```
gh api repos/<R>/actions/runs/<run-id> --jq '.status'      # queued|in_progress|completed
gh api repos/<R>/actions/runs/<run-id> --jq '.conclusion'
```

30s intervals, generous timeout, `notify_on_complete`, and nothing else until it reports `completed`. Twenty overlapping ad-hoc `gh pr checks` reads produce twenty snapshots and no verdict; one bounded poll on the run id produces the conclusion.

### A foreground poll loop dies at the terminal ceiling — arm it as a BACKGROUND watcher instead

A `for … sleep 25` poll run in the foreground returns `Error executing tool 'terminal': timed out after 420.0s` **even when you passed a larger `timeout`** — the tool has a hard ~420s ceiling for foreground calls, so a GPU cell that legitimately builds for 15+ minutes will consume several turns and each dead call returns *no data*. Do not re-run the same foreground loop with a bigger timeout; it fails identically.

Correct shape: write the poll loop to a script under the scratch dir and start it with `background=true, notify=true`. The run returns a `session_id` immediately and the completion notification carries the verdict; a single `gh api …/runs/<id> --jq '{status,conclusion}'` check when the watcher fires confirms it. Give the loop a bounded iteration budget (e.g. `seq 1 240` at 30s ≈ 2h) so it self-terminates instead of polling forever.

Have the watcher print the decision inputs on conclusion — status, conclusion, and the `select(.conclusion!="success")` job-name list — so the tick-vs-hold adjudication needs no second read:

```
gh api repos/<R>/actions/runs/<id>/jobs --jq '[.jobs[]|select(.conclusion!="success")|.name]'
```

While the watcher runs, report the *shape* half of the criterion that is already provable from the live job list (e.g. the one vllm cell present, no GPU cells) rather than idling — a multi-part criterion can be half-graded before the run ends, and the pending half named as pending.

## A run that is `pending` with NO job created is STUCK, not "in flight"

Before you arm a watcher on `status=pending`, prove the run actually has work behind it. A queued
run whose job was never scheduled reads `pending` forever and looks identical to a run waiting for a
runner — but it will never move, so a watcher burns its whole budget on it. Three reads separate the
two:

```
gh api repos/<R>/actions/runs/<id> --jq '{status,updated_at,run_started_at}'
gh api repos/<R>/actions/runs/<id>/jobs           # 404 "Not Found" ⇒ no job was ever created
gh api repos/<R>/actions/runs/<id>/attempts/1/logs # 404 ⇒ nothing ever ran
```

`updated_at == run_started_at` frozen since the run was created, plus 404 on both `/jobs` and
`/attempts/1/logs`, is the stuck signature: the run record exists (it appears in the runs list) but
its first job never materialized. Report it as a **stuck trigger/run that never dispatched**, naming
the run id and its frozen timestamps, and stop polling it — a retry cannot un-stick it. This is a
pipeline/runner finding for the dispatch lane and the planner, not something a review watcher fixes.
Also confirm the negative by reading *what the stuck run should have produced* (e.g. a
`workflow_dispatch` run of the producer at the same head): if no such run exists at the head, the
trigger genuinely never fired, and saying "a producer is in flight" would be a false claim.

**A frozen `updated_at` on the RUN is not stuck when the job list exists and most jobs are `success`.** The
stuck signature needs the 404s above. A run whose `updated_at` has been frozen for minutes while
`/jobs` lists every row and one heavy leg (`linux / unit`, a GPU cell) sits `in_progress` is a **runner
wait**, not a dead trigger: keep polling, and report the already-concluded jobs as proven gates
(`guard`, `lint`, `openspec`, `install`, `agents-read`) with the run as *no verdict yet* rather than
flatly \"in progress\". The decisive row for a body/hygiene criterion is `guard`, so a green `guard` plus
one pending unit leg is a half-graded verdict, not an unknown.

## A run's conclusion binds a criterion ONLY if its head is an ANCESTOR of the live graded head — ancestry is the binding test, not status

Before crediting ANY run (green OR red) to an acceptance criterion or a hold, prove the run's `head_sha` is an ancestor of the head you are grading:

```
gh api repos/<R>/actions/runs/<id> --jq '.head_sha'
git merge-base --is-ancestor <run_head> <live_head> && echo ANCESTOR || echo NOT-ancestor
```

`NOT-ancestor` means the run was dispatched at a **pre-rebase / pre-force-push** head: the branch was rebased or force-pushed after it started, de-parenting that sha. Its conclusion — `completed/success`, `failure`, `in_progress`, or `cancelled` alike — **binds nothing at the live head**. It is stale evidence in its own bucket; report it as "run <id> @ <old-sha> is not an ancestor of <live-sha>, so it proves nothing here", never as a verdict for the criterion. A cell that never ran in a valid channel (a run whose head does not reach the live head) proves nothing regardless of how green it looks.

This is the PARENT rule to the params-equivalent exception below: a params-identical old-head run is the one narrow case where a NOT-ancestor conclusion may be adjudicated (by the owning lane, as a witness — the reviewer still does not tick it). Absent the empty-params-diff proof, a pre-head-move run is simply unbindable.

**Why it bites:** a peer or your own earlier poll hands you a run id that was green and at "the right branch" — but the branch was rebased since, so the green belongs to a commit the live head does not descend from. Ticking off it certifies evidence for a tree that is no longer the head.

## A pre-head-move producer is params-equivalent when the params diff is empty

A runtime criterion that demands "a COMPLETED-SUCCESS run at the current head" can only be judged
against a run whose bind is the current head. After an amend/force-push that moved the head, an
in-progress producer at the *old* head is normally a pre-head-move witness and does not bind. But
when the amend changed no engine params, that producer is building byte-identical inputs, so its
still-running cell is the only remaining path to the bind and its conclusion may be adjudicated:

```
git diff --stat <old-sha> <new-sha> -- containers/engines/params   # empty ⇒ params-identical
```

Report it explicitly as params-identical (empty diff, both shas named) and hand the bind question to
the owner/planner — never tick a runtime box off an old-head run yourself, and never describe a
params-identical old-head run as if it were bound to the new head.

## The derived aggregator does not exist until its source run ends

A verdict/aggregator check (`ci-verdict` and friends) is created by a `workflow_run` trigger *after* the producing run concludes. Absence of that row at the head means **not yet**, never **failed**. A row that is red at the head while its source jobs are green is a **stale** check-run pinned to a pre-fix run at the same sha (`head_sha` matches; the underlying run predates the fix): rerun *the source workflow* so the aggregator re-derives, then quote the fresh conclusion. Do not argue with the stale row, and do not quote it as the verdict.

## A red ci-scope/code-guard RUN does not mean its `guard` job failed — read PER-JOB conclusions before calling a doc/workflow gate red

A "gates stay green" acceptance criterion (docs / workflow / wiring / lint) binds to the shared
**`guard` job's** conclusion, not to the parent run's. A run that concluded `failure` is frequently
`guard=success` and red only on `scope` + its derived `ci-verdict` — the acceptance-gate red on the
criteria you are still holding, which is the DESIGNED hold, not a doc-gate defect. Read the jobs
before grading a criterion:

```
gh api repos/<R>/actions/runs/<run-id>/jobs --jq '.jobs[]|{name,conclusion,id}'
# guard=success, scope=failure, ci-verdict=failure  → doc gates GREEN; the red is check-pr-acceptance
```

Grade the criterion on the `guard` job's own conclusion; report the `scope`/`ci-verdict` red as the
acceptance hold it is (naming the unticked criteria), never as a docs/workflow-gate failure. And a
run created BEFORE your write-back measured the pre-patch state — its red is the state before the
tick, not proof the tick failed (see the post-PATCH re-run rule in
`verdict-and-completion-discipline.md`).

**An issue-body PATCH does not re-trigger PR CI, so the head keeps showing the PRE-write-back red.**
Ticking an acceptance box edits the issue, not the PR head — no workflow fires, and the stale
`guard`/`scope`/`ci-verdict` failure rows sit at the head until something re-runs. Read the attempt
number and the run the aggregator names before calling the head red:

```bash
gh api repos/<R>/actions/runs/<run-id> --jq '{status,conclusion,run_attempt,updated_at}'
gh api repos/<R>/commits/<head>/check-runs --jq '.check_runs[]?|select(.name=="ci-verdict")|.output.summary'
# summary naming run=<id> of an attempt-1 red whose guard has since gone green ⇒ stale, not a defect
```

`run_attempt: 2` with `guard=success` and only a heavy leg pending is a **half-graded head**: report
the already-green gates as proven, name the pending leg as no-verdict-yet, and say the red rows are
pre-write-back snapshots. A peer reading `gh pr view --json statusCheckRollup` minutes after your
tick will still see those rows and report the PR as blocked — that is a snapshot disagreement, not a
contradiction, and the answer is the attempt/lineage read above, not re-ticking anything.

## `mergeable: true` is not `mergeStateStatus: MERGEABLE`

`gh pr view --json mergeable` describes textual conflicts only. The state that governs readiness is `mergeStateStatus`, and `BLOCKED` is what it reads while any required check is red, pending, *or stale*. Report the two separately; never let `mergeable: true` stand in for "ready".

**A `MERGED` PR gets no verdict.** Before posting any owed co-sign, approval or verdict to a head, re-read the PR's state. If another lane merged it while you were polling, the head you were about to judge is gone — posting to it is fabricated evidence on a closed PR. Close the row as moot (the merge is the outcome) instead of posting the verdict.

## Recurring base-gate churn: main advances *during* the run

On a long (multi-minute) `linux / unit` leg, other lanes merge to main while your run is in flight. `check-pr-base` then fails **inside the `make ci-unit` step** (not as its own job) even though your head was cut from a fresh main — because the gate re-resolves the live `origin/main` at job time and it is now newer than your head's parent. This is the single most common red on an otherwise-green head; do not report it as a test failure.

Diagnose by comparing three shas, not by re-reading the failure text:

- the tip the gate *printed* (`measured against origin/main at <sha>` in the log), versus
- `gh api repos/<R>/commits/main --jq .sha`, versus
- your head's parent (`git rev-parse HEAD^`).

If the measured tip is newer than the head's parent and the diff is clean, it is churn, not a defect: fetch the real main (`git fetch origin refs/heads/main:refs/remotes/live/main`, cross-check the API sha), rebase the single atom `--onto` the new tip, re-point the body twin lines, and push with a lease — after a run at the old head has concluded (never force while a run is live).

**Before re-rebasing, check the board has settled.** If open PRs still show auto-merge armed, the tip will move again under your next run and you will rebase a third and fourth time. Confirm no auto-merge is pending (`gh pr list --state open --json mergeStateStatus` all `REVIEW_REQUIRED`/`BLOCKED`, none armed), then rebase onto that stable tip. Sequential re-rebases against a still-draining queue are wasted cycles.

**No armed auto-merge does NOT mean the tip is stable.** In a live fleet the owner automation merges PRs directly (`gh pr view <n> --json mergedBy` reads `asimov-agent`) with no `autoMergeRequest` ever set — so a board reading `REVIEW_REQUIRED`/`BLOCKED` everywhere can still advance main seconds after your settled-check. Four churn-rebases in one sitting all passed that check and still reddened `check-pr-base` when a sibling merged mid-run. Treat the settled-check as necessary, not sufficient: after any rebase, expect the tip may have moved again by the next poll, and re-verify `gh api repos/<R>/commits/main --jq .sha` live at the moment of each push rather than trusting the sha you branched from.

**A rebase onto a tip that has itself been superseded re-reds the same gate — and the gate's `foreign commits (N)` list is the PR's OWN commits, not contamination.** When a PR is rebased onto main tip `T` and any other PR (a sibling lane's, a different PR of your own) merges before the re-run, `check-pr-base` fails with `merge-base(origin/main, HEAD) = T, not origin/main itself` and enumerates `N` "foreign commits": read them (`git log <T>..<HEAD>`) before reporting — they are the PR's own change commits, so the finding is *stale base*, never "this branch carries another PR's diff". The remedy stays the rebase lane's (#845/#1015): record the corrective on the PR, route it to the planner, and do not rebase, push, or arm from the review lane.

`ci-verdict` red on the same run is a **derived echo** of the failing parent leg — never chase it as an independent cause; fixing the unit leg re-derives it.

## Post-merge "main green at merge tip" is proven by a LATER concluded-success run whose head CONTAINS the merge — never by the merge-tip run that reds only on `check-pr-base`

After a PR merges, verifying "main is green at the head that shipped this change" cannot use the CI run dispatched AT the merge tip when that run reds **only** on `check-pr-base` (#845): in a live fleet sibling PRs merge during the run, so the gate re-resolves a newer `origin/main` and fails phantom-staleness on an otherwise-green tree (see the churn section above). A strict per-merge-tip "concluded-success" run frequently **cannot exist** for a multi-vehicle rollout, because each vehicle's merge advances main under the previous vehicle's in-flight run. Do not keep waiting for it.

The binding evidence is a concluded-success run at a LATER main head that has the merge head as an **ancestor** — the opposite direction from the "run-head must be an ancestor of the graded head" rule, which grades a live PR; here the merged content is what must be contained in a green main head:

```
git merge-base --is-ancestor <merge-head> <green-run-head> && echo CONTAINS-merge
gh api repos/<R>/actions/runs/<green-run-id> --jq '{conclusion,head_sha,event}'
gh api repos/<R>/actions/runs/<green-run-id>/jobs --jq '[.jobs[]|{name,conclusion}]'   # every leg present + success ⇒ it is the FULL CI, not a scoped run
```

Cite the green run id + head + the ancestry proof. When verifying several merged rows at once, ONE settled fleet-complete green run whose head descends from ALL their merge heads evidences every row — `git merge-base --is-ancestor <each-merge-head> <green-head>` for each before crediting — so record it once and bind all rows to it. Read the failing merge-tip leg's own log first (per the read-from-job-log rule) to name the phantom cause (`measured against origin/main at <newer-sha>`), then re-anchor to the settled green rather than reporting a content regression or leaving the row open on an impossible run.

**An issue `state_reason: completed` is not proof its stated multi-vehicle closure condition is met.** A rollout tracker can close on the FIRST vehicle's merge (or an unrelated squash `closes #n` line) while later vehicles are still `merged: false`. Before reporting a rollout complete, read each vehicle PR's own `merged` flag (`gh api repos/<R>/pulls/<n> --jq '{state,merged,merge_commit_sha}'`) — the issue `state` is a summary, the PR list is the fact.

## A job that never ran has NO log blob — `skipped` is a designed outcome, not a failure

`gh api …/actions/jobs/<job-id>/logs` answering `BlobNotFound` (or a 215-byte XML error file)
means the job executed no step, so nothing was ever written to the log store — it does NOT mean
the fetch failed or the job crashed. Confirm the shape before treating it as an error:

```
gh api repos/<R>/actions/runs/<id>/jobs --jq '.jobs[]|{name,status,conclusion,nsteps:(.steps|length)}'
gh api repos/<R>/actions/runs/<id> --jq '{event,head_sha}'
```

`steps: []` + `conclusion: skipped` is a job whose job-level `if:` excluded it. Read the
workflow's own condition plus the triggering `event` to name WHY, and report it in a
"skipped — by design" bucket: **skipped is neither green nor red — it proves nothing about the
tree**, so never tick or hold a criterion on it. The concrete recurring case: a `review-verdict`
run on a `pull_request_review` event skips when the review state is `commented`, because that
workflow records only `approved` / `changes_requested`. A COMMENTED-only review lane therefore
always gets a `skipped` review-verdict run and no bot-verdict marker — **by design**, not a
defect and not evidence the review failed to land. That lane's load-bearing record is its posted
review plus the write-back it carried.

## Read a red leg from its job log

```
gh api repos/<R>/actions/jobs/<job-id>/logs --allow-escape-sequences
```

Name the failing gate and its message (`[check-pr-base]`, `[check-pr-sync-line]`, …) in the verdict. A red unit leg on a docs-only diff is nearly always an inherited base gate, not the diff.

## A generic `guard` check-run hides WHICH gate failed — read the failing STEP name

Several distinct body/hygiene gates all report under the single check-run name `guard`, so a red
`guard` row tells you nothing about the cause. The gate identity is the *step* name, read from the
job, not the check-run:

```
gh api repos/<R>/actions/jobs/<job-id> --jq '.steps[]|select(.conclusion=="failure")|{name,conclusion}'
# → {"conclusion":"failure","name":"make check-pr-agents-line (the"}
```

The step name is truncated but names the exact `make` target (here `check-pr-agents-line`, i.e. the
`AGENTS:`/`BASE:` body gate — a *different* gate from `check-pr-sync-line` and from `check-pr-base`).
Do this read before quoting a cause: grepping the log for the word `guard` or `fail` surfaces
GitHub's own step-runner noise (`Prepare all required actions`, `persist-credentials`) and the real
`[check-pr-hygiene] …` message several dozen lines down; the step list puts the culprit first. Only
after naming the gate do you write the remedy, and the remedy must be that gate's own fix
(`check-pr-agents-line` red on a doc-only diff = a missing body line, never a code defect).
