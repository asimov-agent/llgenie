# Reactor-filed issue bodies carry the run id, not the commit title (#2072)

The run-failure reactor files an issue whose body is meant to let a reader reproduce the failed
run — but `issue_body()` filled the `**run:**` Technical field with `run.get('displayTitle')`, the
**commit title** (or the workflow name on a `workflow_run` event), never the numeric run id. So the
issue's own instruction (`gh run view <id> --log-failed`) could not be followed: the identifier
the command needs is exactly what the body omitted. Measured 2026-11-08: three reactor-filed issues
(#2056 #2067 #2070) all carried the same `ci-verdict — …` sentence in `**run:**`. For run
`42428362394` the REST object carried both `id` (`42428362394`) and `display_title`; the reactor
kept the title and dropped the id. Issue #2072 is the fix.

## What changed

`scripts/run_failure_reactor.py::issue_body()` (and its calls through `file_issue()` and `route()`):

1. `**run:**` now carries the numeric run id — threaded `run_id` from `route()` → `file_issue()` →
   `issue_body()` (the run dict from `run_detail()` carries `displayTitle` but not `id`, so the id
   is passed explicitly, with the dict's `id`/`databaseId` as a fallback).
2. The commit title (`displayTitle`) moved to its own `**commit title:**` field — the
   human-readable context stays, just separated from the id.
3. The body's reproduction command (`Failing log tail …`) now cites that same id:
   `gh run view {run_id} --log-failed` — so running the body verbatim reaches the failing log.

The `render_body()` six-section shape (#745) and the line-1 marker (`workflow/job@sha`, the dedupe
key) are unchanged.

## Verified

`tests/test_run_failure_reactor.py` adds `test_the_run_field_and_reproduction_command_carry_the_same_run_id`
which renders a body from a run dict carrying `displayTitle` and no numeric `id`, and asserts the
`**run:**` field contains the numeric run id, the `displayTitle` is NOT what `**run:**` carries, the
commit title appears in its own `**commit title:**` field, and the reproduction command cites that
same id. The negative control was run against the pre-change tree first: it FAILS (the old renderer
puts the displayTitle in `**run:**` and leaves `gh run view <id>`), proving the guard catches the bug.
Full `tests/test_run_failure_reactor.py` passes 31 at the fixing head.

Every reactor-filed issue becomes directly reproducible: the run id in the body is the id the
suggested command uses, so a lane reaches the failing log in one step instead of searching the
workflow's recent runs, and `**run:**`/`**workflow:**` stop being near-duplicates.
