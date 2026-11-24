# Proposal: ci-monitor-superseded-reds

## Why

`make ci-monitor` answers one question per tick — *what on this repo needs an agent right now?* —
and its `MAIN-RED` rule answers it with history: `scripts/ci_monitor.py::main_red_runs` prints
**every** completed `main` run that concluded `failure`/`cancelled`/`timed_out` inside the 72 h
window, including runs a later `main` run of the same workflow already turned green.

Measured on `asimov-agent/llgenie` at main `3afb43704` (2026-11-24,
`gh run list --branch main --limit 100 --json databaseId,workflowName,status,conclusion,updatedAt`):
29 red main runs sit in the window and **20 are superseded** — a newer completed main run of the
same workflow concluded `success` (`auto-merge` 4 of 4, `ci-verdict` 10 of 10, `ci-hf-live` 5 of 5,
security-bot 1 of 1). `make -s ci-monitor` printed 14 of them as incidents, and
`make ci-monitor-triage DRY=1` routed 35 runs (8 `TRIAGE-MAIN` + 27 `TRIAGE-PR`, rc=0) before the
reactor's own `superseded()` guard (issue #565) concluded "filing nothing".

That matters because the snapshot stdout is the hash-gate of the one sanctioned Hermes monitor cron
(`llgenie-planner`, job `857ee38c40ce`, every 30 m): an unchanged snapshot suppresses the agent, a
changed snapshot wakes it. Superseded reds keep the snapshot churning for up to 72 h after they were
fixed, so the tick wakes an agent to triage failures main already resolved. GitHub issue: #3048.

## What Changes

- `scripts/ci_monitor.py` gains `classify_main_runs(main_runs, now, max_age_hours) ->
  (incidents, superseded)`: a main workflow is judged by its **newest completed run on `main`**.
  Only that run can be a `MAIN-RED` incident; an older red in the same workflow group is
  superseded and is no longer an incident.
- `main_red_runs` stays as the incident-only view (it returns the incidents from the classifier),
  so `snapshot_lines`, `triage_incidents` and `build_snapshot` keep one incident definition and the
  triage can never route a superseded run.
- A new `MAIN-SUPERSEDED run=<id> workflow=<name> conclusion=<c> superseded_by=<id>` line shape is
  printed **only** under the new `--include-superseded` knob (`make ci-monitor
  INCLUDE_SUPERSEDED=1`), and superseded lines are never routed by `--triage` even when shown — the
  default snapshot stays incident-only, so the cron hash-gate is not fed history.
- `mk/bots.mk` passes `INCLUDE_SUPERSEDED` through to the script for the human read; the host
  wrapper `~/.hermes/scripts/llgenie_ci_monitor.py` keeps calling plain `make -s ci-monitor`.
- `tests/test_ci_monitor.py` is updated (not only extended): the existing main-red cases move to the
  classifier, and new cases prove red→green is not an incident, red→red still is, an in-flight newer
  run does not supersede, and `--include-superseded` shows the line without routing it.
- The versioned monitor agent behavior `agents/llgenie-planner/prompts/llgenie-ci-monitor.md` —
  the text the sanctioned cron job carries as its prompt — states the same rule, so a tick cannot
  re-learn the old definition: `MAIN-RED` is spelled with the newest-completed-run clause, and
  superseded reds are named as history that is never worked and never routed.
- Nothing reruns, re-dispatches, cancels or merges a pipeline. Out of scope (each its own issue):
  the `PR-CHECKS` half that expands one incident into every historical failed run on a head (#3047);
  re-triaging the issues the old rule already filed, #3042–#3046 (#3049); the engine-bump PR lanes
  whose `guard`/`scope` jobs are red for a missing OpenSpec change and a missing acceptance checklist
  (#3050); and `check-engine-pins-published` reddening `ci-unit` before the lane's own image job has
  published the pins (#3051).
