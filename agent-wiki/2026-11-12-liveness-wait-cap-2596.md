# Registry-liveness publisher-wait: budget + all-event coverage (2026-11-12)

OpenSpec change: `liveness-wait-cap` (MODIFIED requirement on the landed
`registry-liveness-publisher-wait` spec from #2593).

## What was verified

- The landed wait is arithmetically dead for slow publishers: 108 polls × (10 s sleep +
  gh API ≈ 1.5 s) ≈ 20.7–21 min vs the step's 18-minute timeout → cancellation redded the job
  before `publisher_still_running` could be recorded; the defer path was unreachable for
  publishers slower than ~18 min.
- Live evidence at the post-#2593 main tip: liveness run 43313352318 waited 16 m 42 s and the
  same-head publisher (CI run 43313352280, 16 m 51 s) concluded 68 s before the cancellation
  boundary; the run concluded success. Publisher runtimes on main: 16 m 51 s (5ffc7cdc8) …
  40 m 21 s (be92a32695). 18 of the 20 most recent main pushes had ≥1 NOT PUBLISHED gap cell
  (43 total) — a wait was actually needed on those runs.
- Fix implemented in `.github/workflows/registry-liveness.yml`: `WAIT_BUDGET_SECONDS=3600`
  wall-clock `while [ "$SECONDS" -lt "$deadline" ]` loop; `POLL_SECONDS=10`; 60 s registration
  grace → `publisher_none` output (scheduled heads with no publisher exit early); step timeout
  18 → 63 min (budget + slop ≈ 61 min always expires first); job timeout 30 → 90 min; the
  `github.event_name == 'push'` gate removed — polling runs on every trigger event.
- Fleet/filer/dispatch defer machinery (landed via #2593) untouched; only the wait step and the
  wait wiring tests changed.
- Tests: `tests/test_check_engine_pins_published.py` — push-only assertion removed; two new
  wiring tests (all-event coverage + grace exit; budget < step timeout < job timeout ordering).

## Decisions

- Budget 3600 s = ~1.5× the worst measured publisher (40 m 21 s) with a hard ordering test that
  the script's own deadline always fires before the step timeout, so cancellation can never beat
  the defer path again.
- Registration grace 60 s: a same-head ci.yml run is created within seconds of the push (measured
  CI/liveness starts differ by ≤1 s), so a scheduled run whose head never had a publisher exits
  the poll in one iteration instead of burning the budget.
- The scheduled case now also defers sweeps for in-flight/failed same-head publishers — a real
  behavior change, written into the spec delta (MODIFIED requirement) so the referee text matches.

## Current status

Branch `feat/liveness-wait-cap` @ main tip `5ffc7cdc8`; OpenSpec
`make openspec-validate NAME=liveness-wait-cap` exit 0; full hermetic `make test-unit`
**green: 3698 passed, 13201 deselected, rc=0**; module run
`pytest tests/test_check_engine_pins_published.py -m "not network"` **29 passed, rc=0**
(includes the two new wiring tests); `make check-workflows`, `make check-wiring`, `make lint`,
`make check-docs` all rc=0.

Issue: [#2596](https://github.com/asimov-agent/llgenie/issues/2596). PR: this change's own PR
(`closes #2596`).
