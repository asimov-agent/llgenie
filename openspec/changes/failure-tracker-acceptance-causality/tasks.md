# Failure tracker acceptance — tasks

- [x] `scripts/run_failure_reactor.py` generic (non-pins-publish) `acceptance` computed from `is_pins_publish` and naming the failure class, the recurrence prevented, and a negative control (the failing job's `databaseId`)
- [x] green-locally / green-on-the-same-job / `closes #<n>` boxes stay as supporting evidence; pins-publish branch keeps its three publish-specific boxes
- [x] `tests/test_run_failure_reactor.py` extended `test_the_issue_body_carries_the_failing_job_and_log_tail` + new `test_the_acceptance_tracks_the_guard_firing_on_the_job_id`; both FAIL on the pre-change template, PASS on the change
- [x] change-note trio (agent-wiki + docs/changes.d + CHANGES.md) keyed to #2220
- [x] `scripts/issue_body.py::missing()` green for both generic and pins bodies; affected tests 45 passed; full unit suite 3465 passed
