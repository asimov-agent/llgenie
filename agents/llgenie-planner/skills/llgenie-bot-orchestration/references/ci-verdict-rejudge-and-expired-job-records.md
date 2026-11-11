# Re-judging a ci-verdict, and why an old run's job records cannot be

Two separate questions that look like one when a verdict is red on a PR whose legs are green:

1. **Can this run be re-judged?** — does the verdict layer have a manual path, and is the
   underlying job RECORD still intact?
2. **If not, what is the remedy?** — re-run failed jobs, or a fresh run at the head.

Answer both before telling anyone "I'll re-judge it".

## The three remedies are not interchangeable

| Symptom | Remedy | Why |
|---|---|---|
| Judged legs all green, verdict logic counted something it should not have (an absent job, a self-counted row) | **re-judge** via the verdict workflow's manual `workflow_dispatch` path, passing the run id | No content changed; only the verdict arithmetic was wrong. Re-running the whole matrix wastes 30–60 min and rebinds to a new run |
| A leg failed for a transient/infra reason (runner death, docker pull, timeout) | `gh run rerun <id> --failed` | Same head, new attempt, only the failed jobs re-execute |
| The content changed, or the job RECORD itself is gone | **fresh run at the head** (new push, or `gh workflow run <wf>.yml --ref <branch>`) | A verdict can only be computed from job records that still exist |

A verdict workflow that has `workflow_dispatch` with a run-id input is the manual re-judge
path. Confirm it on the tree at the pinned sha before promising it:

```bash
git show origin/main:.github/workflows/ci-verdict.yml | sed -n '/^on:/,/^jobs:/p'
```

If the manual path is absent, the re-judge does not exist and the fix is code on the gates lane.

## The expiry trap: a jobs payload can be a SHREDDED record, not the run's matrix

GitHub garbage-collects per-job records for older runs. `GET /actions/runs/<id>/jobs` can come
back with a `total_count` far below the run's real job count — down to **1**, the verdict's own
row — while the run's matrix had dozens. A verdict computed from that payload reports
`N job(s) ABSENT` and can NEVER be re-judged green: the jobs it needs are not in the record any
more, so every re-judge re-reads the same hole.

**The literal `N job(s) ABSENT` line in a verdict summary IS the expiry symptom.** Do not read it
as "the run had no failing jobs", and do not read it as "the gate is broken". Read it as
"this run id is no longer verdictable".

Measure before promising anything:

```bash
R=<run-id>
gh api repos/<o>/<r>/actions/runs/$R --jq '{status,conclusion,attempt:.run_attempt,created:.created_at}'
gh api "repos/<o>/<r>/actions/runs/$R/jobs?per_page=100" \
  --jq '{total_count, listed:(.jobs|length), names:[.jobs[].name]}'
```

`total_count == listed == 1` with the only entry being a verdict/self row, on a run you know ran a
matrix, is the expired record. Do not quote that payload as evidence about the run's health; quote a
prior on-wire comment if you need the original tally.

Consequence for dispatch: when a tracker or a lane asks for "a green verdict at run X" and run X's
record is expired, the acceptance target is void — the correct instruction is **a fresh run at the
head, then its verdict**, not a re-judge of X. Say the old run id is superseded when you re-point.

## A verdict/`judge` check attached to a merge commit is not automatically about that commit

`ci-verdict`-style workflows also fire on `workflow_run` and can re-judge a run belonging to a
DIFFERENT head (an owner-held PR, a closed branch). Post-merge, such a check appears in
`commits/<merge-sha>/check-runs` while its actual subject is another PR. Before calling a merge-tip
red, resolve the check to its run and read the posted head sha — full procedure in this skill's
`actions-run-attempt-reconciliation.md` ("a check-run listed under a commit can be a verdict about a
DIFFERENT head"). A `judge: failure` on a merge commit whose judged run's head is not the merge sha is
NOT a defect in the merge and must not be filed as one.

## Verify a re-judge was DISPATCHED before reporting it as landed — a new check at the head is not proof

Posting a "re-judge order" on the PR is not a dispatch. Before telling the owner (or another lane) that a
stale verdict is being re-judged, prove a MANUAL run was actually created — the presence of a fresh
`ci-verdict` check at the head proves nothing, because the auto `workflow_run` judge re-fires on its own
and produces a check exactly like a manual one:

```bash
gh api repos/<o>/<r>/actions/workflows/ci-verdict.yml/runs \
  --jq '[.workflow_runs[]|select(.event=="workflow_dispatch")|{id,conclusion:.conclusion//"n/a",created:.created_at,head:.head_sha[0:8]}]|.[0:6]|.[]'
```

- **`event` is the discriminator.** A `workflow_run` entry is the AUTO judge; a `workflow_dispatch` entry is
the MANUAL re-judge. If the filtered list is empty (or has nothing at the PR's head), the maintainer has NOT
yet acted on the order — say so, do not relay it as in-flight. `gh api …/actions/workflows/ci-verdict.yml/runs
--jq '[.workflow_runs[]|select(.head_sha|startswith("<prhead>"))|{event,conclusion}]'` confirms whether any
run judged that specific head at all.
- **A check-run that IS the stale judge reads as red identically to a failed re-judge.** When a `ci-verdict`
check completed red AFTER you posted the order, resolve it to its parent run and read that run's `event` +
`head_sha` before concluding "the re-judge failed for a new reason": an auto judge that fired post-tick but
evaluated a pre-tick `PR_BODY` payload reds for the same stale reason. `gh api repos/<o>/<r>/check-runs/<id>
--jq '{conclusion,completed:.completed_at}'` plus the run's `event`; only a `workflow_dispatch` run whose
judged legs were green but whose arithmetic was wrong is a genuine re-judge failure.
- **A lane's silent/empty reply is not a missing dispatch.** The rebase/maintainer DM channel truncates to 0
  chars routinely; when its reply is empty, do not infer "it ignored the order" AND do not infer "it acted" —
  measure `workflow_dispatch` runs and PR head shas on the wire, and post the durable order on the issue thread
  (the DM gateway max-hops after ~4 messages). Empty DM + no `workflow_dispatch` run = the order is queued on the
  issue, unacted; that is the honest state to report.

## Reporting discipline

- Quote the run id, its `run_attempt`, and the remedy you chose — never "re-judged, should be green".
- A re-judge that lands green produces a NEW check-run at the same head, not a new head sha. Read it
  back by name and `started_at` (dedupe-by-name rule in `actions-run-attempt-reconciliation.md`).
- Never tick an acceptance box on a re-judged verdict alone if the judged legs were not themselves
  green in a current record; the verdict is derived, the legs are the fact.
- Distinguish the three verdict-red states by MEASUREMENT, never by the check name alone: (a) stale-by-timing
  — the check completed BEFORE the AC tick / body edit that fixed the premise (read its `completed_at` vs the
  tick comment's `created_at`); (b) auto-judge still stale AFTER the tick because it re-read a frozen pre-tick
  payload (no `workflow_dispatch` run exists → a manual re-judge is owed and NOT yet dispatched); (c) a genuine
  re-judge failure (a `workflow_dispatch` run exists at the head and STILL reds with green legs). Each has a
  different owner and remedy; quoting "ci-verdict fail" without which one it is wastes the next lane's pass.
