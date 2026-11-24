# 2026-11-23 — monitor incidents: a superseded main red stops being an incident (issue #3048)

## What was verified against the issue

- The inflation was measured live before the change: `make ci-monitor` reported **9** `MAIN-RED`
  lines from 50 completed main runs, and **7** of them were reds a newer completed main run of the
  same workflow had already replaced — 4 `ci-verdict`, 1 `security-bot`, 1 `ci-hf-live`, 1
  `engine-bump`. Only 2 were current. The `triage_incidents()` route set equals the `MAIN-RED` set,
  so every fake incident reached the reactor as a filing candidate; the live tick FILED #3042–#3046
  for exactly the `ci-verdict` family the issue names.
- `classify_main_runs()` in `scripts/ci_monitor.py` is now the single incident rule: group the
  completed main-branch runs by workflow, look only at each workflow's NEWEST completed run
  (`updatedAt` then run id), and file it only when that newest run is
  `failure`/`cancelled`/`timed_out` and inside the age window. An older red of the same workflow is
  superseded and carries `supersededBy=<run id>`. A newer run that has NOT completed supersedes
  nothing — the newest COMPLETED run still decides, so an in-flight lane cannot hide a red.
- The age window stayed its own rule and is unchanged: 0 `MAIN-SUPERSEDED` lines print by default,
  so the cron hash-gate is incident-only unless a human asks for history with
  `make ci-monitor INCLUDE_SUPERSEDED=1` (`--include-superseded`).
- Live read at the head (issue AC 1): `make ci-monitor` prints **2** `MAIN-RED` incidents
  (`45259560508` ci-frozen-reaper, `45326582136` issue-bot) and **0** superseded lines;
  `INCLUDE_SUPERSEDED=1` shows those 2 incidents plus **13** superseded reds each naming its
  superseder (e.g. `45276136174` ci-hf-live failure superseded_by `45304398388`, whose green
  completed run is visible in `gh run list`), and `make ci-monitor-triage DRY=1` routes only the 2
  incidents plus the failed head runs of the 7 `PR-CHECKS` PRs.

## Decisions

- Supersession is per-workflow, not per-attempt: a red whose newer run is in progress remains an
  incident, and a red whose newer run is red (the `ci-verdict` cascade) is an incident too — only
  the NEWEST one is, so one failing workflow files one issue instead of a family of them.
- `MAIN-SUPERSEDED` is history text, never an incident: `triage_incidents()` reads
  `main_red_runs()` (the incident class), so the knob cannot change routing.
- `tests/test_ci_monitor.py::test_old_red_runs_age_out_of_the_window` was UPDATED, not duplicated:
  it now plants three distinct workflows so the age window and supersession are proven independent.
  New tests cover red→green supersession, red→red cascades, the in-flight case, the age window on
  the newest completed run, and "shown but never routed" under `--include-superseded --triage`.

## Agent behavior mirror

- `agents/llgenie-planner/prompts/llgenie-ci-monitor.md` (the text the sanctioned
  `llgenie-planner` cron job `857ee38c40ce` carries as its prompt) now spells `MAIN-RED` with the
  newest-completed-run clause and states that a superseded red "is NOT in the snapshot at all …
  never treat those as work and never route them (issue #3048)". Without this mirror a tick would
  re-learn the old definition from the prompt even after the code lands.

## Re-measured after `main` moved

- At the lane head sitting directly on `origin/main` `3afb43704`: `make -s ci-monitor` printed **4**
  `MAIN-RED` incidents (`45213506777` registry-sync, `45242135444` engine-bump, `45259560508`
  ci-frozen-reaper, `45328814726` issue-bot — a new red superseding `45326582136`) and 7
  `PR-CHECKS`, against **14** incidents reported by the pre-change monitor on the same main commit.
  Consequence recorded on #3049: staleness is not permanent — registry-sync and engine-bump are red on
  their newest completed main run again, so the re-triage asks "is the workflow's newest completed main
  run still red?" and closes only when it is green.
- Side findings filed as their own issues instead of widening this lane: #3047 (PR-side routing cost),
  #3049 (re-triage of #3042–#3046), #3050 (engine-bump PRs red at `check-pr-openspec-change` +
  `check-pr-acceptance-form` on 7/7 lanes), #3051 (`check-engine-pins-published` reads pins before the
  lane's own `engine-build-pr-trigger` job publishes them).

## Current status

OpenSpec change `ci-monitor-superseded-reds` validated (`make openspec-validate` rc=0); 16 monitor
tests green in the full `make test-unit` battery. Branch `feat/ci-monitor-superseded-reds`, PR
#<PR> closes #3048. No workflow file changed; no pipeline was started, rerun, or cancelled by this
change.
