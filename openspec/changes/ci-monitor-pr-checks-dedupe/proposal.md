# Change: the PR-checks monitor leg routes representatives, not history

## Why

Issue #3047: `scripts/ci_monitor.py::triage_incidents` routes **every completed failed run ever
recorded on a PR head**, so one triage tick spent most of its time re-reading runs that the reactor
had already seen. Measured on `main` at `3afb43704`
(`make -s ci-monitor-triage DRY_RUN=1`, 2026-11-24T04:4xZ): **27 `TRIAGE-PR` routings** for the
seven review-held engine-bump PRs #3029–#3035 — the reactor's own memory
(`scripts/run_failure_reactor.py::filed`, `file_only=True`) then discarded them one by one, and
`run=<id>` never appeared in any issue because the head's runs are not the runs that produced a
fixable report. The same tick re-routed a run that was still **pending** (`45281314211` on
`chore/engine-bump-ollama`, created 2026-11-23T22:36:37Z, `status=pending`): a pending run belongs
to the queued-alarm lane (`make queued-alarm`, `.github/workflows/queued-alarm.yml`), not the
reactor. And a routed red carried no **owning lane**, so a reviewer could not see that a failed PR
pipeline must be fixed on its own branch (AGENTS.md: "a failed PR pipeline is fixed ON ITS BRANCH").

## What Changes

- A **representative per failing check bucket** is routed instead of every historical failed run on
  the head: candidates are ordered newest-completed-red-first across the head's workflows, reads per
  workflow are capped (`MAX_RUNS_PER_WORKFLOW`), and a run is routed only while it still stands for a
  bucket no already-routed run covers. Buckets are matched through one normalized key
  (`_check_key`: lower-case, whitespace collapsed, the workflow's `— <description>` suffix dropped,
  a `lane / job` name reduced to its job part), because `gh pr checks` reports `linux / unit` while a
  run reports the job `linux / unit`. The declined history and the buckets nothing explained are both
  printed (`PR-ROUTE pr=<n> head=<sha> routed=<k> suppressed=<m> aged=<a>[ uncovered=<buckets>]`) so
  the coverage claim stays readable instead of silent.
- A PR head with a **pending/queued** run produces no routing and no job read: the tick prints
  `TRIAGE-QUEUED pr=<n> head=<sha> owner=queued-alarm runs=<ids>`, naming the lane that owns it.
- Every routing names the **owning lane** — the PR's head branch — in its verdict
  (`owner=<headRefName>`), so a red PR-lane check on an open bump PR reads as work that lands on
  that branch.
- The head read stays **one** read: `runs_on_head(sha)` returns every run on the head with its
  `status` (the routing plan needs the pending rows and decides which rows are incidents), replacing
  the completed-only `failed_runs_on_head(sha)` the triage leg used (AGENTS.md: no second command path
  over the same head).
- The `PR-CHECKS pr=<n> head=<sha> failed=<k>` snapshot line is **unchanged**: what the monitor
  reports stays the same, only what gets routed changes.

## Out of Scope

- Fixing the reds on #3029–#3035 themselves — each bump PR is its own lane.
- The main-red half of the same incident, already landed as `feat/ci-monitor-superseded-reds`
  (issue #3048).
