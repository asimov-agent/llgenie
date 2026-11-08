# engine-build-trigger-404-reresolve

## ADDED Requirements

### Requirement: a 404 poll is re-resolved by head_sha+branch, never waited out as "not concluded"

When the poll of a dispatched producer run's run-id endpoint returns a 404 (empty / non-JSON
read), the trigger MUST re-resolve the run through the run-LIST endpoint keyed by the `head_sha`
+`branch` the trigger knows (it just dispatched there), instead of treating the 404 as "the run has
not concluded" and waiting out the full `wait_min` bound. A producer that already concluded
`success` is then reported as SUCCESS immediately, with the resolved run id recorded.

WHEN the run-id poll for the dispatched producer returns a 404 AND the run-list read keyed by
head_sha+branch shows that same run concluded `success`
THEN the trigger stops immediately, prints the OK line naming the resolved run id, and returns 0 —
without waiting out `wait_min`.

#### Scenario: a 404-then-visible producer concludes SUCCESS via head_sha re-resolution

- **Given** a `push=true` dispatch whose run-id poll returns 404, a `--wait-min` far beyond the
  first poll, and a head_sha+branch run-list read that now shows the same run `success`
- **When** the trigger awaits that run
- **Then** it returns rc 0 immediately (not at the deadline), prints `producer run 77 success` with
  the resolved run id, and never reports a bound expiry
- **Test:** `tests/test_engine_build_trigger.py::test_404_poll_is_reresolved_by_head_sha_to_success`
  drives a fake `gh` whose run-id poll 404s and whose head_sha list read answers the run's real
  success verdict with `--wait-min 120`, and asserts the OK line and rc 0. On the pre-fix code this
  test FAILS (the 404 is treated as "not concluded" and the far bound would be awaited), proving the
  guard catches the #2059 poll-visibility wait.

### Requirement: the expiry message names a 404 visibility race vs a real conclusion

When a dispatched producer's poll is a 404 and its run never becomes visible even after head_sha
re-resolution, the trigger's failure line MUST name that the producer's last known status was a 404
(never visible), so a reader can tell a poll visibility race from a concluded build failure.

WHEN the wait bound expires with the awaited run's LAST known read being a 404 (never visible even
via head_sha re-resolution)
THEN the failure message states `never became visible (last poll 404)` and that it is a poll
visibility race — never a bare `last status <None>` or a verdict-shaped "never concluded".

#### Scenario: a never-visible 404 run fails at the bound naming the visibility race

- **Given** a `push=true` dispatch whose run-id poll 404s, head_sha re-resolution also finds nothing,
  and `--wait-min 0` (so the bound expires on the first poll)
- **When** the trigger's wait bound expires
- **Then** it fails rc 1 and the message names the 404 visibility race
  (`never became visible (last poll 404)`, `poll visibility race, not a concluded build failure`)
  instead of a bare last status
- **Test:** `tests/test_engine_build_trigger.py::test_404_visibility_is_named_on_expiry` stubs
  `_resolve_run_by_head_sha` to keep returning `{}` with `--wait-min 0` and asserts both 404-race
  phrases in the stderr. A real-conclusion expiry (the run visible but never terminal) still prints
  the pre-existing `never concluded, last status …` line (locked by
  `tests/test_engine_build_trigger.py::test_wait_expiry_names_the_run_and_last_status`).
