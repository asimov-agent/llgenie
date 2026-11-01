# 2026-11-02 zero-job-pending trigger re-pointed (issue #1442)

The zero-job-pending monitor shipped by #1412 (closed #1410) existed as source but could **never
fire at current head**: `zero-job-pending.yml` triggered only via `workflow_run: queued-alarm /
types: [completed]`, and `queued-alarm.yml` is one of the 14 workflows `disabled_manually`
(measured 19:40Z via `gh workflow list`). A disabled source never runs, so the workflow_run event
never fires — the runner-starvation naming #1410 demanded stayed silent forever. Planners measured
the strongest proof: `GET /actions/workflows/zero-job-pending.yml/runs` → `total_count: 0` (never
executed a single run since #1412 merged it), while queued-alarm's last run predated #1412.

This change re-points the monitor's `workflow_run` trigger from the disabled `queued-alarm` onto the
**active** `ci-requeue` (completes every 30 min on `:15/:45`), the sibling runner-health healer.

- `.github/workflows/zero-job-pending.yml`: trigger block + header rationale now name `ci-requeue`
  (`name:` verbatim) instead of `queued-alarm`; explains why (disabled_manually source, budget
  exhausted, riding an active sibling's cadence rather than owning a minute —
  `test_no_workflow_shares_a_minute` #275/#301 stays green). No re-enable of queued-alarm (owner's
  call, flagged in #1442).
- `docs/BOTS.md`: the `make check-zero-job-pending` help text now records the ci-requeue trigger and
  the #1442 reason.
- No new `schedule:` minute owned; the 13-remaining disabled workflows unchanged.

Verified: `scripts/check_workflows.py check` rc=0 — queued-alarm's completion stays routed (the
run-failure-reactor roster already watches it; the `workflow-run-uncovered` and
`workflow-run-unknown-name` rules are satisfied — no exemption added, only the trigger name edited).
The monitor fires on the next ci-requeue completion; acceptance proof is the fresh run id on the PR.
