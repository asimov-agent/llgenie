# Failure-tracker acceptance names a cause class and a negative control (#2220)

The reactor's `issue_body()` laid down the SAME three generic acceptance boxes for every failed
job, so a PR that simply re-ran the failing job could tick all three even when the failure class
recurs — six open trackers (#2156 #2157 #2164 #2185 #2184 #2160) were in fact one cause class filed
six times, and every re-judgement spawned yet another identical tracker. Issue #2220 is the fix.

## What changed (`scripts/run_failure_reactor.py`)

The generic (non-pins-publish) `acceptance` list is now computed from `is_pins_publish` and names:

1. **the failure class** the tracker names — `workflow/failing-step` taken from the failing step's
   logged error in the Technical tail, not the job name;
2. **the recurrence prevented** — a negative-control test that FAILS on the pre-fix tree and PASSES
   on the fix, proving the guard holds this class;
3. **a negative control** — the failing job's `databaseId`, which the guard must fire on.

The green-locally / green-on-the-same-job / `closes #<n>` boxes stay but are demoted to supporting
evidence. The pins-publish branch keeps its three publish-specific boxes unchanged.

## Verified

`tests/test_run_failure_reactor.py` extended `test_the_issue_body_carries_the_failing_job_and_log_tail`
to assert the cause-class + negative-control shape and added
`test_the_acceptance_tracks_the_guard_firing_on_the_job_id`. Both FAIL on the pre-change template and
PASS on the change (the negative control was run against the old tree before the fix, proving the
guard catches the bug). `scripts/issue_body.py::missing()` is green for both the generic and the
pins body; `test_run_failure_reactor.py` + `test_issue_body.py` + `test_check_issue_body.py` pass 45,
and the full unit suite passes 3465 at the fixing head.

A symptom patch that only re-runs one job can no longer name the cause class or the negative control,
so it fails at least one box — the class stops spawning one tracker per re-judge.
