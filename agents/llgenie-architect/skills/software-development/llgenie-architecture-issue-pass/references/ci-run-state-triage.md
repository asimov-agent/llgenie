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
