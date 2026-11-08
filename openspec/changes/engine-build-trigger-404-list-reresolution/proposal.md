## Why

`scripts/engine_build_trigger.py` polls `repos/{repo}/actions/runs/<id>` for the producer run it
just dispatched. When that endpoint answers **404**, the API returns its error body on stdout:

```json
{"message":"Not Found","documentation_url":"…","status":"404"}
```

`json.loads` succeeds, so the await loop received a `run` dict whose `status` is the literal string
`"404"` — which matches **none** of the loop's terminal branches (`pending`/`queued`,
`cancelled`/`skipped`, `success`, `completed`). The loop therefore kept polling to the wall-clock
bound and failed:

```
[will] FAIL engine=surogate: wait bound (60 min) expired — producer run 42428385314
       never concluded, last status 404
```

Measured on #1982 (head `7c429bde`, base `d7f57cfa`): producer run `42428385314` had actually
concluded **`success`**. A green PR was red for an hour on a poll-visibility race, indistinguishable
from a real build failure. Filed as issue **#2059**, which this change fixes.

## What changes

- `_run_verdict()` reads one run's `{status, conclusion, completed_at}`. On a 404 from the
  single-run endpoint it **re-resolves the same run from the run LIST** (`/actions/runs?per_page=100`,
  selected by id), which is readable earlier than the run's own resource, and returns the resolved
  verdict — naming the resolved run in the log so the decision is recorded, not silently taken.
- When neither endpoint yields a verdict, the 404 is returned instead of an indistinguishable
  `None`, so a failure message can name a **poll-visibility race** distinctly from a real expiry.
- The await loop calls `_run_verdict()`; the existing wall-clock bound still bounds an unresolvable run.

## What does not change

The wait bound, the terminal branches, the exit codes and the `in_progress`-holder logic
(#917/#621) are untouched. A 404 is never read as success by itself — success requires a real
`conclusion` from the run list. No gate is weakened, and no re-dispatch is added: the
re-resolution is a read.
