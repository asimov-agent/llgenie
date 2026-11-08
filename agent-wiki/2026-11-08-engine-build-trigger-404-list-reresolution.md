# A dispatched producer's 404 is a poll race, not a verdict (issue #2059)

## The defect

`scripts/engine_build_trigger.py` polls `repos/{repo}/actions/runs/<id>` for the dispatched
producer's verdict. A 404 from that endpoint returns the API's **error body on stdout**:

```json
{"message":"Not Found","documentation_url":"…","status":"404"}
```

`json.loads` succeeds, so the old code got a `run` dict whose `status` is the literal string
`"404"`. That matches **none** of the await loop's terminal branches (`pending`/`queued`,
`cancelled`/`skipped`, `success`, `completed`), so the loop simply kept polling until the
wall-clock bound and then failed:

```
[will] FAIL engine=surogate: wait bound (60 min) expired — producer run 42428385314
       never concluded, last status 404
```

Measured on #1982 (head `7c429bde`, base `d7f57cfa`): that producer run `42428385314` had actually
concluded **`success`**, and the trigger waited the full 60-minute bound and failed. A green PR was
red for an hour on a poll-visibility race, indistinguishable from a real build failure.

## What changed

`_run_verdict()` reads one producer run's `{status, conclusion, completed_at}`, and on a 404 from
the single-run endpoint **re-resolves the same run from the run LIST** (`/actions/runs?per_page=100`,
selected by id) — an endpoint that is readable earlier than the run's own resource. A resolved
`success` concludes the wait immediately with the resolved run id named. When neither endpoint
yields a verdict, the 404 verdict is returned rather than an indistinguishable `None`, so the
failure message can NAME a poll-visibility race distinctly from a real-conclusion expiry.

The await loop now calls `_run_verdict()` and keeps the existing bound: a run that stays invisible
is still bounded by the wall clock, and the message still says `last status 404`.

## Why this is safe

- **No gate is weakened.** The wait bound, the terminal branches, the exit codes and the
  `in_progress`-holder logic are unchanged; this adds a resolution route, it does not relax a verdict.
- **A 404 is never read as success by itself.** Success requires a real `conclusion` from the run
  list; an unresolvable run stays `404` and the bound still fails it.
- **No new dispatch.** The re-resolution is a read; the trigger never re-dispatches on a 404.

## Proof

- `tests/test_engine_build_trigger.py` models both endpoints (a `single_run_404` fake for the
  invisible single-run read, a `list_missing` fake for an id invisible in the list too).
- The success-path test uses `--wait-min 120` deliberately: on unfixed code it would poll the full
  bound, which is exactly the defect — so the red proof is taken from the instant (`--wait-min 0`)
  expiry test, whose message is the issue's own quote.

## Files

- `scripts/engine_build_trigger.py` — `_run_verdict()` plus the await loop calling it.
- `tests/test_engine_build_trigger.py` — the fake-`gh` routes and the regression tests.
- `openspec/changes/engine-build-trigger-404-list-reresolution/` — this change.
