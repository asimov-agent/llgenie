# engine-build-trigger-success-conclude

## ADDED Requirements

### Requirement: a SUCCESS producer is terminal — the trigger concludes promptly with a verdict

When `_dispatch_and_wait` observes its awaited producer run with `conclusion` `success`, the wait MUST
end immediately (not at the `wait_min` deadline) and `check` MUST print the OK line naming the run —
`[will] OK engine=<e>: producer run <id> success` — and return 0. A run's `conclusion` is only ever
populated once the run has finished, so `success` is the final verdict even when the `status` field
the poll reads is a stale/mid-flight snapshot (`in_progress`) or a run whose `completed_at` is null.
This is the green mirror of `#1936`'s cancelled/skipped-terminal rule: the terminal decision comes from
the CONCLUSION, never from the status field alone.

WHEN the awaited producer run reports `conclusion` `success`
THEN the trigger stops polling immediately, prints `[will] OK engine=<e>: producer run <id> success`,
and returns 0 — without waiting out `wait_min`.

#### Scenario: a success producer with an in_progress status snapshot concludes rc 0

- **Given** a `push=true` dispatch whose new run reports `status: in_progress, conclusion: success` and `--wait-min 0`
- **When** the trigger awaits that run
- **Then** it returns immediately (not after the deadline), prints `producer run 77 success` on stdout, and `rc == 0`
- **Test:** `tests/test_engine_build_trigger.py::test_success_producer_terminates_even_with_status_not_completed`
  drives a fake `gh` whose new run is `in_progress/success` with `--wait-min 0` and asserts the success
  line and `rc == 0`. On the pre-fix code this test FAILS FAST (the deadline expires and `rc == 1`),
  proving the guard catches the #1994 hang.
