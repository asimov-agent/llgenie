# Stale-ref and transient reds: what is a real defect, what is a measurement artifact

## A stale/advanced main can make a guard read a false red — check the CURRENT base before blaming the PR

2026-11-01 #1412, twice:
- The `check_pr_closing` guard (`make check-pr-closing`) reds when the runner's `base..rev` sweeps a commit that is really ON main. First time the runner base itself was stale (`--base 391df770` predating main `d94d3280`, whose #1414/#1415 squashes leaked in). Second time the base was right (`d94d3280`) but main ADVANCED mid-run to `07342a11` (the #1411 merge, itself a `(#1411)`-suffixed squash claiming #1402), so the runner's MERGE-REF checkout merged the head against main-at-glance and pulled that post-base main commit into `base..rev` — its `(#1411)` subject became a "claim" the PR neither makes nor must close.

Proof recipe (run target `check_pr_closing.py` directly, not `make` — make echoes):
```
python3 scripts/check_pr_closing.py check --body-file /tmp/pr-body.md --base <CURRENT upstre-main sha> --rev <head sha>
# rc 0 at current main base = the PR is clean; reproduce the CI red at the stale/base+rev combo to prove it is the range, not the PR body/commits
```
`git fetch upstream main` first; `git merge-base --is-ancestor <main sha> <head>` rc=1 means the branch is BEHIND and the correct remedy is a REBASE onto current main, not editing the PR or rerunning.

## A red linux/unit on a PR head is often a stale base, not a code regression

**The `check-pr-base` stale-base red (issue #845).** The guard leg (not your
change's own unit test) fails inside `linux/unit` and/or the `guard` rollup with:

```
[check-pr-base] FAILED: HEAD is NOT cut from origin/main —
  its merge-base with origin/main is <old-main-sha> ...
```

The cause is never your diff — `origin/main` advanced past the tip you cut from.
Two of your own PRs cut at the same old sha go red together; that co-firing is
the tell.

Fix — **on your OWN vehicle only**: `git fetch upstream main`, `git rebase
upstream/main` in the PR's own worktree (clean = ahead 1 / behind 0, merge-base
with origin/main now == origin/main), re-verify your own gates on the rebased
tree (lint, check-docs, the workflow-validity tests in the CI container), then
`git push --force-with-lease` to the same fork branch. The old run's red does not
clear — you replace it; wait for the FRESH run at the new head (see
`monitoring-check-rollups.md`).

**Ownership nuance (resolves the standing "do not rebase" rule):** the lane-wide
do-not-rebase rule targets **another lane's PR**. A stale-base red on *your own*
dispatch/vehicle is yours to rebase — that is the required repair, and
`llgenie-pr-merge-conflict` was not dispatched for it. A stale-base finding on
someone else's branch is still a report to that lane, not a rebase you perform.
Never report a stale-base red as "your change broke unit tests" — quote the
`check-pr-base` line, name the merge-base sha and current `origin/main` sha, and
state the fix is a rebase, not a code change.

## Flake vs persistent defect: the RERUN AT THE SAME HEAD is the discriminator — "passes offline" is not proof

A red that fires on every recent main push looks like a flake family, but a live-network (or any)
failure can be a **persistent product defect** that merely re-fires. Settle it with the acceptance's
own test: rerun the failing job at the SAME merged head and read attempt 2.

```bash
gh run rerun <run_id> --failed          # GitHub refuses while the run is still in_progress — wait for it to complete
gh api repos/<o>/<r>/actions/runs/<run_id> --jq '{status,conclusion,run_attempt}'   # attempt must be 2
gh api repos/<o>/<r>/actions/jobs/<job_id>/logs | sed -E 's/\x1b\[[0-9;]*[mK]//g'   # compare the failure line to attempt 1
```

- **Attempt 2 fails IDENTICALLY at the same sha → persistent defect, NOT a flake.** Say so and route
  it for a product fix. A step that fails its own rerun cannot be healed by retry/debounce (a #1250-style
  retry+debounce design would only skip the next run and hide it) — do not fold it into a flake-family audit.
- **Attempt 2 passes → flake confirmed**; the retry/robustness issue is the right home.
- Never report "flake" from a single red, a check name, or the fact that it also reds on other tips — a
  defect that fires on five consecutive pushes looks identical to a flake until you rerun one.

**Before accepting an audit's "add retry + debounce" remedy, prove the family is actually flaky — read the failing job LOG, not the annotation.** An issue that groups several main-only reds under "no actionable failure text, exit 2 / Node20 warning" is usually describing **annotation truncation**, not flakiness. Open each failing job's log (`gh api repos/<o>/<r>/actions/jobs/<job_id>/logs`, strip `\x1b\[...m`): when the log carries the target's OWN cause line — `... the committed plan https://… is gone`, `make: *** [Makefile:<N>: <target>] Error 1`, a specific assertion — the step is a **deterministic, drift/defect red**, and the real defect is that the check-run annotation dropped that line to the generic `Process completed with exit code 2`. Two consequences: (a) a blanket auto-retry or debounce would re-red the same deterministic cause (or skip it and hide it) and re-spawn the separator-issue churn it claims to stop — never accept "retry" as the fix for a red whose log names a cause; the actionable fix is surfacing the target log tail into the annotation, so flake-vs-drift is decidable from the check run. (b) Confirm each named red's true class before disposition: a red whose later attempt-2 at the same sha also failed is a persistent defect to route, not a flake; one that names the tracked dead-link drift IS that drift issue, not a new flake — say so and do not file a flake family over it. A single-occurrence red with no same-head follow-up success is an unproven transient, and "unproven" is not "flaky".

**"It passes offline on my machine" is NOT evidence of a flake — the CI runner is a different machine.**
A live gate that reads the runner's own resource profile (total RAM / headroom / card) can select a
DIFFERENT candidate set on the CI host than on this workstation, so a clean local run says nothing about
why CI chose a set that violates an invariant (e.g. a per-provider "high + lower" pick coming back only
32 bytes apart under live size jitter). Report it as a **machine-card-dependent product defect** with the
log's actual assertion and sizes, not as "flaky — passes locally".

**A `--check --snapshot` (hermetic) run CANNOT observe dead links — an exit-0-with-notes there refutes
nothing about a live-gate red.** The generator's hermetic probe (`_snapshot_probe`) returns `PROBE_OK`
unconditionally — its own docstring: "the hermetic gate reports the drop as a NOTE and never a failure.
Deciding dead-vs-reachable is the live seam's job." So the SAME committed link that hermetic prints as
"still reachable (ok) … kept, not a failure" can probe 404/410 on the live seam
(`make check-quant-catalog LIVE=1` → `scripts/gen_trending_quant_catalog.py --check` WITHOUT
`--snapshot`, i.e. exactly what ci-hf-live runs). When someone re-classifies a data-drift red as
"gate-logic over-flag" based on a snapshot run, run the LIVE seam and quote its rc + the exact dead-URL
failure lines — the snapshot instrument is evidence about notes, not about liveness. Also separate the
carried-over reachable entries (all probe 200 → notes, never the gate's failure) from the genuinely dead
404/410 plan (a real failure), because both appear in the same hermetic NOTE list and conflating them is
the error. (2026-11-04 #1712: the 7 UI-seen carry-over entries all answered 200 on direct HEAD; the
actual live-seam failures were two laguna-xs-2-1/MLX chat_template.jinja links answering 404/410.)

**A live-network step that reads the LIVE upstream is not fixed by a committed-data refresh.** Two reds
can look like the same "catalog drift" family and be unrelated: a step that regenerates a committed
snapshot fixes steps that replay that snapshot, but does NOT fix a step that hits the live API at runtime
(two different flakes/defects, two fixes). Identify which each step reads before claiming one refresh
covers both.

## After another lane re-rebases your PR, re-run the gates at the NEW head before reporting green

A rebase lane advancing the branch means the head you verified before is NOT the head under review:
measured, a head verified green (LIVE seam + hermetic + module tests) was superseded by a re-rebase onto a
newer main, so the accepted state was a different sha than the one proved. Never carry an earlier head's
verdict forward — fetch the branch into a temp ref (`git fetch <remote> <branch>:refs/remotes/<tmp>`),
`git worktree add --detach /tmp/vwt <tmp-ref>`, run the actual gates THERE (the make targets / the LIVE
seam + hermetic + the covering test modules), then report the NEW head sha with its own gate output. Same
discipline as accepting a handover — a head you did not push yourself is measured, never inherited.

## A cancelled run reads `fail`; a job that cannot load has zero jobs and every rollup reads clean

A cancelled run and a failed run both surface as `conclusion=fail` — never attribute a negative
conclusion from the status badge alone. A workflow that cannot even load (`name` typo, bad trigger)
files no run, so its rollups read clean and its absence is invisible; a check that never starts and a
check cancelled mid-flight are indistinguishable from an alarm. Report from the LOG, not the colour:
open the failing job's log, or (for absence) verify the workflow really ran by listing runs and
confirming the expected jobs each concluded. An owner-disabled producer reds its dependents' gates even
when the producer itself shows nothing — measure the consumer.

## A branch the guard has already verified stays green across a gratuitous rerun; the flip side: never cite a run as green that you have not read the conclusion of

Touching only the PR body or committing a no-op does not re-trigger the jobs that already passed —
calling the same conclusion "green" twice proves nothing about a fresh state. If you want a gate's
current verdict, wait for a run at the CURRENT head and read its conclusion; a cached/older run's green
is history, not a current claim. Never report a run as green from its existence or from the check name —
you must have read `status=completed` and the `conclusion` field for that exact run id.

## A suspended/failed delivery to a lane and a stuck background poll loop both look like "the tool is wedged" — a single bounded API read distinguishes real state from the wedge

Never run a multi-minute `for i in; do gh run view; sleep 60; done` poll loop in foreground that the runner may background — it wedges the whole session's terminal for every later command. Prefer a single bounded `gh run view --json status,conclusion`; if still in_progress, end the turn and re-check on the next wake/notification. If the terminal wedges, keep evidence on the board and deliver the exact one-liner the recipient can run. (See terminal-wedge-and-click-loop.md.)

## A re-classified "carry-over / gate-logic" fix is refuted by the gate's own LOG — quote the 404/410 failure lines

When a re-dispatch claims a live-gate red is "gate-logic over-flag — the catalog is correct, only the
carry-over policy needs a code change", do not implement that change on the claim. Run the LIVE seam
(`scripts/gen_trending_quant_catalog.py --check` WITHOUT `--snapshot`, = `make check-quant-catalog LIVE=1`)
at the CURRENT head and read what it actually names:

```
FAIL: ... is stale (run make sync-quant-catalog)
  qwen3.8-flash-next-125b/SGLang: the committed plan https://.../UD-....gguf is gone (the link answers 404/410) — nothing serves it, drop it with make sync-quant-catalog
  laguna-xs-2-1/MLX: ...chat_template.jinja is gone (answers 404/410) ...
```
- A line ending `answers 404/410 — nothing serves it` is a GENUINE dead plan — the very case the brief
  says must stay red ("still reds on a genuine removal"). N such lines refute "the catalog is correct".
- The 7 UI-visible carried-over entries the re-dispatch names all probe HTTP 200 and sit in the NOTES;
  they were never the failure, so a code change that "stops flagging reachable carried-over plans"
  addresses zero real failures and only teaches the producer to ignore the dead ones too — the precise
  gate-weakening the standing rule forbids.
- Run the LIVE seam at the ACTUAL vehicle's head too (it may already be green there): 2026-11-04 #1712
  main `6ce5a2e4` reds on 19 lines / 6 dead URLs, while the vehicle #1720 head `74e45475` runs rc=0 /
  0 dead links. Green at the live seam is the acceptance; an already-green open PR is not duplicated.
  Resolution: #1720 merged as `031b652a` 2026-11-04; merged-tip `ci-hf-live` check-run success (run
  `41928673686`, completed 23:11:41Z); repo's own gate at main `031b652a`/`a9f05258` LIVE_RC=0 dead=0.
  So #1712 closed after the merge, not by any lane-authored gate change — the data-drop was the fix.
- Check whether the gate ALREADY locks the distinction before writing a code change. `tests/
  test_quant_catalog_compare.py` pins it via the real `compare()`/`carry_over()` against a real loopback
  socket: reachable-still-served and gated-401 → note/non-failure; genuinely-dead 404 → failure — that
  test's own docstring: *"Acceptance 2: the gate must not be weakened into 'whatever the search dropped
  is fine.'"* Sure found 17 passed at `6ce5a2e4`. When a dispatch asks to "stop flagging reachable
  carry-over", the code and its tests already do that; only the genuinely-dead 404/410 case remains, and
  weakening it breaks the locking test. State that a conflation is refuted by a passing locking test, not
  argued.

## A "ci-verdict" red that names a still-in_progress run is the #1250 attempt-supersession shape, not the gate racing a live run

`ci-verdict` fires on `workflow_run types:[completed]`, so it cannot judge a run still in progress. A red
check-run that names a run id whose row reads `in_progress` at the verdict minute is attempt-1 (cancelled
by `cancel-in-progress`) on the SAME shared id as the live attempt-2 — GitHub shares the run id across
attempts, so the red is correct for the cancelled attempt and the attempt-2 success supersedes it green.
Rule, verification commands and the reader-side decision table: `run-attempt-and-cancelled-neutral-gates.md`
*Diagnosing a rout of this shape*.

