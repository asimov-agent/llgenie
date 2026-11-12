# Tasks: liveness-wait-cap

- [x] `registry-liveness.yml`: publisher-wait step drops the `github.event_name == 'push'` gate
      and polls the same-head `ci.yml` run on every trigger event, with a bounded
      registration-grace exit when no same-head publisher exists.
- [x] `registry-liveness.yml`: the poll loop is bounded by an elapsed-seconds deadline
      (`WAIT_BUDGET_SECONDS=3600`, `SECONDS`-based) strictly smaller than the step timeout;
      step `timeout-minutes: 63`, job `timeout-minutes: 90`.
- [x] Update `test_push_run_waits_for_the_same_head_publisher_before_the_manifest_check` to
      lock the all-event wait and the same-head poll; add
      `test_publisher_wait_runs_for_every_trigger_event` and
      `test_publisher_wait_budget_always_expires_before_its_step_timeout`; adjust the
      push-only docstring in `test_scheduled_and_successful_publisher_keep_the_dispatch_contract`.
- [x] Full unit suite green (`make test-unit`), `make openspec-validate NAME=liveness-wait-cap`
      passes, gates green (`make lane-preflight`).
- [ ] Mirror issue #2596's body to the measured landed semantics (18-min bound, 16 m 42 s live
      near-miss, 40 m 21 s worst-case publisher) with ticked acceptance criteria.
