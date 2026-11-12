# Proposal: liveness-wait-cap

## Why

Issue #2596. The landed publisher-wait (change `registry-liveness-publisher-wait`, PR #2593)
fixes the push race with two properties that do not hold under measured runtimes:

1. **The 18-minute step bound kills the wait before its own defer path can run.** The loop
   is `for _attempt in $(seq 1 108)` with `sleep 10` per iteration — 108 iterations need
   ≥ 1080 s of pure sleep plus API time (~21 min), while the step carries
   `timeout-minutes: 18`. Any publisher longer than ~18 min cancels the step mid-loop, so
   `publisher_still_running=true` is never written and the job REDS — the deferral is dead
   code for slow publishers. Measured publisher runtimes: 16 m 51 s (CI #5568, run
   43313352280) and 40 m 21 s (CI #5565, measured 19:22:16Z→20:02:37Z). Live near-miss on
   liveness run 43313352318: the wait step consumed 16 m 42 s of its 18 m bound and the
   publisher concluded 68 s before the step timeout would have cancelled it.

2. **The wait is gated to `push`, so a scheduled run has no protection at all.** Cron fires
   3× daily; a cron that lands inside the 17–41 min publisher window of the current main
   head reads GHCR mid-publish and takes today's unmitigated path: hard-fail + issue filing
   + sweep dispatch against tags that are mid-publish — the exact class #2592 removed for
   push.

## What Changes

- The publisher-wait step runs for **every trigger event** (push, schedule, workflow_dispatch
  rerun): it polls the same-head `ci.yml` run whenever one exists. A run with no same-head
  publisher (the normal scheduled case) proceeds immediately after a bounded
  registration-grace poll instead of racing blindly.
- The wait is bounded by a **wall-clock budget**, not a fixed attempt count: the loop tests
  `SECONDS` against a `WAIT_BUDGET_SECONDS` deadline so the script always reaches the
  `publisher_still_running` defer path BEFORE its step timeout. Budget 3600 s (60 min)
  exceeds the measured worst-case publisher runtime (40 m 21 s) with margin; step
  `timeout-minutes: 63`; job `timeout-minutes: 90`.
- The defer semantics (suppress hard-fail, no filing, no dispatch while in flight) and the
  failed-publisher refusal are UNCHANGED — they merely become reachable for slow publishers
  and now also apply to scheduled runs that actually catch a publisher in flight. A wait that
  hits its budget is never a silent green: it emits a `::warning::` annotation naming the
  deferral (budget, head SHA, "this run verified nothing") beside the job-output defer banner.
- Update the two tests that lock push-only waiting (`test_push_run_waits_for_the_same_head_
  publisher_before_the_manifest_check`, `test_scheduled_and_successful_publisher_keep_the_
  dispatch_contract`) and add tests locking the all-event step + grace exit and the
  budget-vs-timeout relationship (`test_publisher_wait_runs_for_every_trigger_event`,
  `test_publisher_wait_budget_always_expires_before_its_step_timeout`).

## Not covered

- Speeding up the main publisher run itself (ci.yml runtime tuning) — separate concern.

## Impact

- Affected specs: `registry-liveness-publisher-wait` (MODIFIED)
- Affected code: `.github/workflows/registry-liveness.yml`,
  `tests/test_check_engine_pins_published.py`
