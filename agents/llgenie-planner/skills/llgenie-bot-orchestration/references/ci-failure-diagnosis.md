# Reading CI state: what actually failed, and what only looks like it

## Job logs ARE readable — the empty response is a `gh` guard

```
gh api repos/<owner>/<repo>/actions/jobs/<job_id>/logs
#  -> "the response contains terminal escape sequences; pass --allow-escape-sequences"

gh api repos/<owner>/<repo>/actions/jobs/<job_id>/logs --allow-escape-sequences \
  | sed 's/\x1b\[[0-9;]*m//g' \
  | grep -E "^(FAILED|E  )" | head -40
```

That one flag turns every red into a named assertion. Do not tell a lane "logs are unavailable" and let it reproduce blindly — check the flag first.

`gh run view <id> --log-failed` refuses while the **run** is in flight even when the **job** has completed; use the API above instead.

## `run.status` lies; jobs tell the truth

A run can report `status: queued` for an hour while twenty jobs hold runners and one step is executing. An alarm keyed on `run.status` reads a hang as "waiting for capacity" and sleeps through it. Read **job-level** fields: `status`, `conclusion`, `runner_name`, `started_at`, and step transitions.

## Four different "not green" states — never collapse them

| state | meaning | lever |
|---|---|---|
| `failure` | an assertion failed | fix the code/test |
| `cancelled` | someone/something killed it | never a pass; re-run or address the canceller |
| `queued` + `runner_name: null` | never dispatched | capacity, not the diff |
| `pending`/`skipped` | not evaluated | waiting |
| `mergeable_state: UNKNOWN` | GitHub is still recomputing after a base move | wait — it is **not** a conflict; only `CONFLICTING`/`DIRTY` needs a rebase |

A cancelled job is not a failure and not a pass. A queued job with no `runner_name` is capacity. A job that started and then was cancelled is a third thing again. Quote the field you measured.

## A `completed/failure` run with zero jobs is a workflow that cannot load

`timeout-minutes` is illegal on a `uses:` job. The workflow fails to parse before any job exists, so the run is `completed/failure` with **0 jobs** and every status rollup reads `fail=0` — the PR looks clean, has no red check, and can never run. A PR that cannot execute is worse than a red one.

```
gh api …/runs/<id> --jq '.status, .conclusion'
gh api …/runs/<id>/jobs --jq '.jobs|length'    # must be > 0 for a run to be evidence of anything
```

Ceilings belong inside the called workflow's own jobs, never on the caller. Gate it structurally: a workflow-shape test asserting no `uses:` job carries `timeout-minutes` (and that the file parses into ≥1 job) catches what no rollup can.

## Timeouts interact with the queue, not with the work

A job without `timeout-minutes` inherits GitHub's 360-minute default, so "hung" and "slow" are indistinguishable for six hours. Symptoms worth pricing rather than describing: provisioning steps taking seconds followed by one step with no transition for tens of minutes; a consumer job (`install`, `wait-for-image`) polling a fixed budget while its producer cells are still queued — the wait expires and reports "not found", which reads as a bad tag.

When adding ceilings: set each **above** the longest job it calls, and pin the caller/callee relation in a test in both directions — a caller ceiling tighter than its callee kills a healthy run and looks exactly like a red.

## A rerun requires a completed run

```
gh run rerun <id>            # only on completed; in flight -> 403 "This workflow is already running"
gh run rerun <id> --failed   # re-runs only failed/cancelled jobs
```

On an in-flight hung run the only lever is `cancel`, which destroys whatever it had earned — so prefer waiting when the run's successes are worth more than the runner, and cancel when the verdict is moot (closed/merged PR).

## A run for a closed or merged PR is worth nothing

Before cancelling or rerunning anything: `gh pr view <n> --json state,mergedAt`. A merged PR's matrix is history; a live run on one is holding capacity that a pending PR needs. With a small runner pool, one stale long run is an outage for the whole queue.

## Repro before ruling: a failure that exists on the base is not the PR's

Run the failing files on a pristine detached worktree of the base commit and compare counts. Six failures on `main` will otherwise be attributed to six different PRs — and each lane will "fix" a copy of the same stale assertion. A log names the **ref it ran on**: quoting a branch log as evidence about `main` converts a PR defect into a repo defect.

## When a change moves a shape, grep the suite for that shape's spelling

Inline script → make target, a renamed key, a new `needs` edge, a matrix axis: anywhere a shape moves, some assertion pins the old spelling and reds a correct fix. Search the tests for the old token **before** pushing, and prefer asserting the wiring (`make -s <target> ARG=` , `step["env"]`, the recipe) over the literal text it replaced.
