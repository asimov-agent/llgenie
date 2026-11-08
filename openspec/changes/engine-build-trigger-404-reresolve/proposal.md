# engine-build-trigger-404-reresolve

## Why

`scripts/engine_build_trigger.py::_dispatch_and_wait` treats a **404** from the run-id poll as "the
run has not concluded yet" and waits the entire `wait_min` bound (default 60 min) before failing,
even when the dispatched producer already concluded `success`. Measured on #1982 (head `7c429bde`,
base `d7f57cfa`), trigger run `42428364793`: the producer `engine-build … push=true engine=surogate`
(producer run `42428385314`) concluded **success** (`engine-build-surogate-cuda: success`), yet the
trigger logged `[will] FAIL engine=surogate: wait bound (60 min) expired — producer run
42428385314 never concluded, last status 404`. A green PR was red for an hour on a poll-visibility
race, and `mergeStateStatus` read `BLOCKED` with nothing distinguishing "producer 404'd but
succeeded" from "producer genuinely failed" — blocking #1982's auto-merge despite 13/13 other checks
passing.

The root cause is that a 404 on a just-dispatched run is a visibility/propagation race (the polling
token cannot yet read the run's own resource), not a verdict. It must never be waited out as "not
concluded".

## What changes

`scripts/engine_build_trigger.py`'s await loop detects a 404 poll (the run-id read returns empty /
non-JSON) and re-resolves the run through the run-LIST endpoint keyed by the `head_sha`+branch the
trigger KNOWS (it just dispatched there — the list endpoint is readable earlier than the run's own
resource). A producer that already concluded `success` is then reported as SUCCESS immediately,
with the resolved run id recorded, instead of polling out the full bound. If the run is never
visible even after re-resolution, the expiry failure names the 404 visibility race explicitly —
`never became visible (last poll 404) … poll visibility race, not a concluded build failure` — so a
reader can tell a poll race from a real build failure. `last_was_404` is tracked on the awaited-run
return and carried into the expiry message.

A regression test (`test_404_poll_is_reresolved_by_head_sha_to_success`) drives the wait loop with a
run-id poll that 404s and a head_sha list read that now shows the run `success`, asserting the
trigger concludes rc 0 with the resolved run id named. A second test
(`test_404_visibility_is_named_on_expiry`) drives the never-visible case and asserts the expiry
message names the 404 race.

## Out of scope

- The general wait-bound tuning is tracked separately in #1844; this change is only the
  404-as-not-concluded handling.
