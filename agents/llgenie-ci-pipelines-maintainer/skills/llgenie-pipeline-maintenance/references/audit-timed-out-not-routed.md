# Audit finding: a `timed_out` run is a red no routing consumer remediates (#1465)

Filed 2026-11-01 at `70288bab` upstream/main during the workflow-robustness sweep (dispatch on
#1420). A run whose job exceeded its `timeout-minutes` concludes `timed_out` at run level, and no
routing consumer remediates it:

- `scripts/run_failure_reactor.py::route()` lines 492-509 only act on `conclusion == "failure"`
  (`cancelled` has its own supersession path, issue #843); every other conclusion — including
  `timed_out` — prints `not a failure, nothing to do` and returns 0: no issue filed, no fix-bot
  dispatch.
- `.github/workflows/fix-bot.yml:334` gates the repair sweep on `conclusion == 'failure'` only.
- `scripts/auto_merge.py:243` `RED_CONCLUSIONS = {"failure", "timed_out", "startup_failure"}` — so a
  timed-out PR is BLOCKED from merging (auto-merge defers it forever).
- `scripts/ci_verdict.py` marks a skipped/cancelled/absent selected job red, so the head is
  red-visible — but visible-red is not a remedy consumer.

Net: a `timed_out` run stalls its PR with a red check, auto-merge defers, and no lane files an issue
or starts a repair. Distinguish from the #1250 cohort (#1420 cancelled/stale-head, #1422
run_attempt, #1423 cancelled-as-neutral-green) which do NOT name the `timed_out` route. The reactor
test suite has zero `timed_out` cases.

Remedy (for the implementer queue, tagged `agent:implement`): let `route()` treat a run-level
`timed_out` like `failure` (a verdict, unlike a supersession-able `cancelled`); widen fix-bot.yml's
sweep conclusion test to include `timed_out`; add hermetic reactor tests mirroring the `cancelled`
cases at `tests/test_run_failure_reactor.py:466-501`. Never implemented in the audit pass;
check-docs owns a change that touches `scripts/` + a workflow `if:` (needs an agent-wiki note +
docs/changes.d/ fragment + CHANGES.md regeneration, issue #1123).
