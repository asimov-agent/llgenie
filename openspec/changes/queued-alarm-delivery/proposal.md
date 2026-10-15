# queued-alarm-delivery — proposal

Issue: [#294](https://github.com/asimov-agent/llgenie/issues/294) (the silent report), context #254

## Why

`scripts/queued_run_alarm.py` exists to make a stuck runner loud: a job whose `runs-on` label matches
no machine stays `queued` forever, the run never concludes, and every PR's checks sit at "pending"
with no signal anywhere (#254). The sweep itself works — but its `--comment` half posts to

```
POST /repos/{owner}/{repo}/issues/{run_id}/comments
```

and **a workflow run id is not an issue number**. The POST returns `404`, the result is discarded
(`capture_output=True` with no return-code check), the job still exits 0, so the alarm's report is
written **nowhere** while the job looks green. The dedupe read is the same URL, so "comment once per
run" cannot hold either. Measured on `main@472de9f`: `gh api /repos/asimov-agent/llgenie/issues/<run id>`
→ `{"message":"Not Found","status":404}`.

## What Changes

- **The report lands where a human reads it.** A run that reports on a PR is commented on **that PR**
  (the issues-comments endpoint, which serves a PR number correctly); a run no PR tracks
  (a schedule/push run) contributes its runner **labels** to a fallback issue — **ONE open issue per
  stuck label**, deduplicated by a marker in the body, because a missing runner is a property of the
  label, not of one run.
- **The PR is resolved from the run's HEAD BRANCH, because the two direct routes do not work**
  (both measured live on gh 2.102.0): `gh run view --json` has no `pullRequests` field at all
  ("Unknown JSON field: pullRequests"), and the REST run object's `pull_requests` array comes back
  EMPTY for a fork-PR run — the shape this alarm sees (`/actions/runs/38761102690` → PR 277,
  `…/38731475236` → PR 170 are resolved by branch). A read that fails is reported, not swallowed.
- **Dedupe markers name their subject**: `<!-- queued-run-alarm: run <id> -->` for a PR comment (a newly
  stuck run is still news) and `<!-- queued-run-alarm: label <label> -->` for the fallback issue.
- **A delivery that fails is loud, never silent**: every POST/create checks its return code, the
  failures go to stderr as `DELIVERY FAILED: …`, and the process exits **3** (new: stuck jobs whose
  report did not land) instead of the old exit 1 that read as success.
- **`--dry`** prints what `--comment` would post and posts nothing; `make queued-alarm DRY=1` exposes it.
- The make target's help line, the README's alarm line and the workflow's step name state the delivery
  (AGENTS.md README-sync rule).

## Not covered

- **#254 itself** (the `macos-15-intel` queue with no matching runner) — this change only makes its
  symptom visible where a maintainer will see it; adding a runner is a separate decision.
- **Runs that were already superseded/cancelled** — the sweep reports the current state of the queue.

Refs: #254 (the cause this reports), #289 (the push-cancellation rule), #296 (the sibling
silent-checker finding).
