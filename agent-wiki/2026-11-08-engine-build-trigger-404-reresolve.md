# 2026-11-08 — engine-build-pr-trigger re-resolves a 404 producer poll (#2059)

## The defect

`scripts/engine_build_trigger.py::_dispatch_and_wait` treated a **404** from the run-id poll as
"the run has not concluded yet" and waited the full `wait_min` bound (default 60 min) before
failing, even when the dispatched producer had already concluded `success`. Measured on #1982 (head
`7c429bde`, base `d7f57cfa`), trigger run `42428364793`: the producer `engine-build … push=true
engine=surogate` (run `42428385314`) concluded **success** (`engine-build-surogate-cuda: success`),
yet the trigger logged `[will] FAIL engine=surogate: wait bound (60 min) expired — producer run
42428385314 never concluded, last status 404`. A green PR was red for an hour on a poll-visibility
race; `mergeStateStatus` read `BLOCKED` with nothing distinguishing "producer 404'd but succeeded"
from "producer genuinely failed", blocking the PR's auto-merge despite 13/13 other checks passing.

Root cause: a 404 on a just-dispatched run is a visibility/propagation race (the polling token
cannot yet read the run's own resource), not a verdict — and it must never be waited out as "not
concluded".

## The change

- On a 404 run-id read (empty / non-JSON), `_dispatch_and_wait` re-resolves the run through the
  run-LIST endpoint keyed by the `head_sha`+`branch` the trigger KNOWS (it just dispatched there —
  that endpoint is readable earlier than the run's own resource) via `_resolve_run_by_head_sha`.
- A producer that already concluded `success` is then reported as SUCCESS immediately (rc 0), with
  the resolved run id named — never waited out to the bound.
- The awaited-run return carries `last_was_404`; if the run is never visible even via re-resolution,
  the expiry message names the race: `never became visible (last poll 404) … poll visibility race,
  not a concluded build failure` — distinct from a real-conclusion expiry (`never concluded, last
  status …`).

## Evidence

`tests/test_engine_build_trigger.py` 15 passed (13 prior + 2 new:
`test_404_poll_is_reresolved_by_head_sha_to_success` — drives a 404 run-id poll + a head_sha list
read answering real success with `--wait-min 120`, asserts rc 0 and the resolved run id — and
`test_404_visibility_is_named_on_expiry` — a never-visible 404 with `--wait-min 0`, asserts the
404-race phrasing). The first fails against the pre-fix code (the 404 would be awaited out to the
bound). `git diff` touches the script, its test, this openspec change and this note + its fragment.
Implements #2059.
