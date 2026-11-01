# fix(reactor): route a run-level `timed_out` conclusion like `failure` (#1465)

A run killed by a job timeout is a verdict, not a cancellation: the job was dispatched, ran out of
wall-clock, and its conclusion `timed_out` enters `RED_CONCLUSIONS` (it blocks auto-merge). Yet
`run_failure_reactor.py::route()` only acted on `conclusion == "failure"`, so a timed-out run stalled
its PR red, auto-merge deferred, and no lane filed anything — a red with no routing consumer (the
#1250 class, issue #1465).

This change routes a run-level `conclusion == "timed_out"` through the same path as `failure`:
- route A: the pushable same-repo PR is claimed + `fix-bot` is dispatched via `fix-bot.yml`;
- route B: a no-PR run files ONE deduped issue.

`cancelled` is explicitly NOT folded in: a killed run's verdict is still a verdict, and the existing
`cancelled` supersession path (#843) is preserved separately. The behavioural change spans
`scripts/run_failure_reactor.py`, the `fix-bot.yml` workflow called on the new conclusion, and the
`docs/BOTS.md` reactor description.
