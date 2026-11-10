# Triage of a CI run's state

Depth for the SKILL.md rules on pushing, rerunning, cancelling and reporting run outcomes. Every command here
is read-only except the cancel, and every number quoted in a report must come from a `completed` reading.

## 1. Is the run still alive, and is it hung or starved?

```bash
gh api repos/<owner>/<repo>/actions/runs/<run> --jq '"\(.status)/\(.conclusion // "-") attempt=\(.run_attempt) updated=\(.updated_at)"'
gh api repos/<owner>/<repo>/actions/runs/<run>/jobs \
  --jq '.jobs[] | "\(.name) | \(.conclusion // .status) | runner=\(.runner_name // "NONE") | \(.started_at)"'
```

Read it as three different states, not one:

| observation | meaning |
|---|---|
| `status=queued`, jobs `success` + `queued`, **`0 in_progress`** | **starved** — waiting for runners, will not advance on its own |
| jobs `in_progress` with `runner_name` set, `updated_at` frozen many minutes | **possibly hung** — measure step transitions (below) before saying so |
| `status=completed` | only now is `conclusion` and any job count quotable |

`updated_at` freezing is a weak signal on its own; GitHub does not rewrite it for every step. The step table is
the real instrument.

**`run.status` itself lags the jobs and is not a liveness signal.** Measured on one run: `status` read `queued`
for 55 minutes with `updated_at` frozen while **20 jobs held runners** and the gate job had been executing for
53 minutes. A later run showed the milder form — `status=queued` with `guard=success` already recorded. An
alarm keyed on `run.status` therefore classifies an executing run as "waiting for capacity" and sleeps through a
hang; read `runner_name` and the step table per job, and when filing the alarm defect require a **job-level**
read with a negative control that replays the `queued`-plus-held-runners shape.

## 2. Step-transition timing — the only sound way to call a job hung

```bash
gh api repos/<owner>/<repo>/actions/jobs/<job-id> \
  --jq '.steps[] | "\(.number). \(.conclusion // .status) \(.started_at // "-") → \(.completed_at // "-") \(.name)"'
```

Interpretation: if the provisioning steps finish in seconds and one step then shows `in_progress` with a
`started_at` tens of minutes old and no transition, the job is **stalled**. Quote both halves — "four steps in
27 seconds, then one step for 51 minutes" — because either number alone is arguable and the pair is not.

**Check `timeout-minutes` before concluding anything:**

```bash
python3 -c "import yaml,sys; d=yaml.safe_load(open('.github/workflows/pipeline.yml'));
print({j: c.get('timeout-minutes','ABSENT') for j,c in d['jobs'].items()})"
```

No key means GitHub's **360-minute** default, so a hung job yields no red check and holds its runner. That is a
defect worth filing on its own, worded as "the pipeline cannot bound this", not "the job is slow".

## 3. Rerun legality

```bash
gh run rerun <run>            # → run <n> cannot be rerun; This workflow is already running
gh api -X POST repos/<owner>/<repo>/actions/runs/<run>/rerun
                              # → 403 {"message":"This workflow is already running"}
```

Both succeed **only on a `completed` run**. So the honest options for a hung in-flight run are exactly two:
wait for it to finish or hit the default, or cancel it — and cancel destroys every job already green. Never
present `rerun` as a remedy without that caveat. `--failed` (or a per-job rerun by id) exists but still
requires a completed run, and re-queues every cancelled row, including rows that starve.

## 4. Cancelling: the pool test

Before cancelling "to clear the queue", list both sides:

```bash
gh api repos/<owner>/<repo>/actions/runs/<blocked>/jobs \
  --jq '.jobs[] | select(.conclusion == null) | "\(.name) \(.status) runner=\(.runner_name // "NONE")"'
gh api repos/<owner>/<repo>/actions/runs/<candidate>/jobs \
  --jq '.jobs[] | select(.status == "in_progress") | "\(.name) runner=\(.runner_name)"'
```

- If the blocked run's pending rows **all** already hold runners, nothing you free helps it.
- If the candidate is holding a **Linux** runner and the blocked run waits on **macOS** (or vice versa), the
  queues do not cross: cancelling buys an idle slot nobody wanted at the price of every success in the matrix.
- A run on a **closed PR** is the clean exception: its successes are worth nothing, and its runner is worth
  something. Cancel it, then verify `completed/cancelled` and report the counts.

## 5. Reporting an outcome

- **Cancelled is never a pass and never a failure.** Report four buckets — success, skipped, cancelled,
failure — and name every cancelled job when the run mattered, with its `runner_name` (empty means it was never
assigned one).
- A reported total is a hard assertion: sum the buckets against `.jobs | length` before writing it down.
- **Durations are quotable only from completed jobs.** An `in_progress` job's elapsed time is a snapshot; if you
need a baseline for a timeout budget, use only the runs that reached a conclusion and say how many there were.
- **Logs are readable — `0 bytes` is the CLI's ANSI guard, not an empty log.**

  ```bash
  gh api repos/<owner>/<repo>/actions/jobs/<job-id>/logs --allow-escape-sequences \
    | sed 's/\x1b\[[0-9;]*m//g'
  ```

  Same job both ways: `0` bytes without the flag, `86848` with it. `gh run view --log-failed` fails identically
  for the same reason. Try the flag before concluding the cause is undiagnosable; an empty flagged read on an
  old run is *retention*, a different statement. Only then fall back to a local reproduction in the test image.

## 6. A cancelled run answers no question about the code

A run killed mid-flight cannot distinguish "this scenario fails" from "this scenario never ran". If a probe's
control rows were cancelled alongside its test rows, it is not evidence for any hypothesis — restate what it
does show (nothing) rather than reading the cancellations as a result in the direction you wanted.

## 7. A red run does not prove the HEAD is red — live-state gates

Some gates read **live repository state at merge time**, not only the checked-out tree: the acceptance gate
fetches the linked issue's `## Acceptance criteria`, the closing gate fetches the live PR body, the hold gate
reads labels. Those inputs can be edited by a **different lane, outside the branch**, so a run that failed at a
head can be green at the *same* head once the issue is ticked. The commit never changes; the verdict does.

So before treating `ci-scope failure at <head>` as work — and long before pushing a "fix" commit — reproduce
the gate yourself at that exact head with the LIVE payload:

```bash
git worktree add --detach ../<wt>/<name> <head>
gh pr view <n> --json body --jq .body > /tmp/pr-body.md
cd ../<wt>/<name> && PR_BODY=/tmp/pr-body.md PR_BASE=origin/main PR_HEAD=HEAD make check-pr-<gate>
```

Green there means the remaining gap is only a **green run id**, and the two push-free remedies are
`gh run rerun <id>` (same sha, no new commit, no re-cut matrix) or leaving it to the lane holding the branch's
live `bot-claim`. A push would re-prove something already true and cancel the matrix doing it.

Corollary — **read which job actually failed before naming the gate.** A run's failing job can be a *different*
gate from the one in the dispatch: measured, `check-docs` was green inside a run whose `scope` job redded on
`check-pr-acceptance`. Read `gh run view <id> --json jobs --jq '.jobs[]|"\(.name) \(.conclusion)"'`, then the
failing job's log — never assume the dispatch named the gate that failed.

## 8. A dispatch names a base sha: it is a claim about time

An instruction is written against an earlier reading, so its sha is usually an **ancestor** of the real head by
the time you act. Re-resolve in the acting turn and state the relationship rather than silently substituting:

```bash
gh api repos/<owner>/<repo>/commits/main --jq .sha      # the real head, now
git merge-base --is-ancestor <named-sha> origin/main && echo "<named> is an ANCESTOR of main"
```

And check whether the dispatch's scope has **already landed** before writing anything:

```bash
gh pr view <n> --json comments                          # bot-claim:, auto-merge: deferred, other lanes' repairs
git show --stat --format="" <head>                      # does this commit's own stat already contain the artifact?
gh run list --branch <head> --status in_progress --json databaseId --jq length   # 0 = nobody is racing you
```

Measured once: a dispatch named a stale base AND an artifact (change-note + `docs/changes.d/` row) that a rebase
lane had already committed at the current head, with a live `bot-claim` still in TTL. The correct answer was a
comment proving the scope satisfied — "dispatch stale on two counts, no push" — not a duplicate commit. When a
`bot-claim` with an unexpired TTL names another actor, the branch is theirs: report and hand off, do not race.
