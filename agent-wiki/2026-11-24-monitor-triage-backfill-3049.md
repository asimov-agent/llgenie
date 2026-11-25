# Monitor triage backfill: `make monitor-triage-sweep` re-reads the reactor's past filings (issue #3049)

## What was verified against the spec

OpenSpec change `monitor-triage-backfill` (specs: `host-ci-monitor`). Issue #3049's problem was
measured: six open `run-failure-reactor` filings named runs that no monitor snapshot would report as
incidents today, because issue #3048's single-incident rule keeps only each workflow's NEWEST
completed `main` run — so a filing for a red a newer completed run replaced is history, not an
incident. The lane lands the backfill leg that re-reads those filings against the live read.

- `scripts/monitor_triage_sweep.py` — the filing filter is the reactor marker alone (`<!-- run-fixer:`,
  the reactor's own dedupe key); `agent:ci-pipelines-maintainer` is recorded on the verdict as
  `pipelines_lane` rather than required, because #3044 is open with the marker and no labels at all.
  The Technical block's `**workflow:**` / `**run:**` fields are parsed back with bullet-tolerant regexes (measured on issue #3042, where the reactor
  writes them as `- ` bullets — a stricter pattern silently reports `no-newer-run` for every filing).
- The verdict rule is `ci_monitor.classify_main_runs` with the age window off, so a sweep verdict and
  a monitor snapshot can never disagree (issue #3048). `live_index` returns three halves — the
  newest completed RED per workflow, the filing-run → superseder map, and the newest completed
  `main` run per workflow — the last one so a filing whose run aged out of the read window still
  reads as `superseded-by <run>` instead of falling into the weaker `no-newer-run`.
- Write half: superseded → claim comment, a supersede comment naming the superseder, `gh issue close`,
  `bot_claims.done_comment`; live → the current red recorded on the issue (skipped when the body
  already names that run id, so re-runs don't re-comment); `no-newer-run` → left open, nothing sent.
  A live `bot_claims.occupant` claim skips the filing. DRY by default: `emit` is a recorder and the
  writes appear only as `SWEEP-MODE dry writes-planned=<n>`; `APPLY=1` swaps in `execute`.
- The leg never touches a pipeline (AGENTS: queue-pumping is forbidden) — its `gh` verbs are
  `issue list/view/comment/close` and `run list` reads, and the tests assert the dry argv carries no
  rerun/cancel/dispatch/merge verb.

## Key decisions

- A re-verification sweep over the reactor's own filings, not a new incident detector, and its
  classification goes through the monitor's classifier rather than a second rule.
- `gh api` is used for the per-issue comment read (paginated), never `gh issue view --comments` — the
  flag combination errored in the #3047 lane.
- Live board read (dry): rc=0, `SWEEP-TALLY re-read=6 superseded=1 live=3 no-newer-run=2
  skipped-claim=0` with `SWEEP-MODE dry writes-planned=7` — every issue #3049 names was re-read: #3045
  read `superseded-by 45483683805`, #3042/#3046/#2254 read live, #3043/#3044 read `no-newer-run` (their
  named run sits outside the 100-run `main` read, so the sweep refuses to guess).
- Applied read (`make -s monitor-triage-sweep APPLY=1`): rc=0, `SWEEP-MODE applied writes=7` with the same
  tally. #3045 is CLOSED — claim comment, then a comment naming `45483683805` as the superseder, then
  `gh issue close`, then the `<!-- bot-done: monitor-triage … closed superseded run 45259560508 -->` stamp;
  #3042 / #3046 / #2254 stay OPEN with the current red run recorded on the issue; #3043 / #3044 received
  nothing.

## Current status

Branch `feat/monitor-triage-backfill`, PR open against upstream `main`. `tests/test_monitor_triage_sweep.py`
11 passed (zero network); `make -s monitor-triage-sweep` rc=0; lint / check-import-roots /
check-package-layers / check-wiring / openspec-validate / check-docs re-measured at the pushed head.

Refs: #3049 (this lane), #3048 (the supersession rule it reuses), #3042–#3046 (the filings it re-reads).
