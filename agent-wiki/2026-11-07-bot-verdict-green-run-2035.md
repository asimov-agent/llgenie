# bot-verdict run= slot is gated to a concluded-green run (issue #2035)

## What was closed

The bot-verdict marker's `run=` slot — the #1551 record of WHICH run measured that head — was
written but never *verified* to be a green run at the head. `review-verdict.yml` resolved it as the
newest **completed** run (any conclusion), and `bot_verdict.post` validated `--run` only as `\d+`, so
an `approve` verdict could name a failed/cancelled run as its evidence anchor. The merge gate's own
`no_concluded_green`/`failing_checks` were unaffected (they re-read the head's runs independently);
this closed the *record* link, not the *merge* link.

## Fix (verified)

- `review-verdict.yml` `Resolve the run that measured this head` now selects
  `select(.status=="completed" and .conclusion=="success")` — a head whose newest completed run is
  red but an older one succeeded records `run=<the green id>`, never the red one.
- `scripts/bot_verdict.py::post` now verifies `--run` resolves to a concluded-SUCCESS pull_request
  run at `--head` before posting an ACCEPTING verdict; rc 2 with the reason otherwise. A `changes`
  verdict is unchanged (it names the problem run).
- `tests/test_bot_verdict.py` negative controls: approve citing a red run at the head is refused,
  approve citing a run not at the head is refused, `changes` may cite any run, and the workflow's
  run-resolution pin reddens when `.conclusion=="success"` is dropped. Proven both ways: reverting
  the producer gate fails `test_post_approve_refuses_a_run_that_concluded_failure_at_the_head`
  (assert 0 == 2), and the pre-fix workflow fails
  `test_the_workflow_run_resolution_is_pinned_to_concluded_success`.
- Gates at the fixing head: `make test-unit`, `make check-workflows`, `make check-wiring`,
  `make lint` all exit 0.

## Status

Implemented on branch `agent/issue-2035-bot-verdict-green-run`; one PR closes #2035.
