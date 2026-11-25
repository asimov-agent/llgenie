# Proposal: supersession-aware re-triage of reactor-filed main-red issues (issue #3049)

## Why

`scripts/run_failure_reactor.py` files one marker-deduped issue per failure CLASS, and its
`superseded()` guard (issue #565) only stops NEW filings. Before issue #3048 fixed the monitor's
`MAIN-RED` rule, the sanctioned monitor tick fed it superseded history, so the filings themselves are
stale: #3042 (`security-scan`), #3043 (`registry-sync`), #3044 (`engine-bump`), #3045
(`ci-frozen-reaper`) and #3046 (`issue-bot`) are all OPEN, and at least two of them name main runs
that a newer completed green main run already replaced. Nothing re-reads them, so the board the agent
picks its next lane from carries fake work items whose evidence run is history.

## What Changes

1. New leg `scripts/monitor_triage_sweep.py` (stdlib-only, unit-testable, no LLM): it pages the open
   issues and keeps the reactor filings — the body marker `<!-- run-fixer: … -->` IS the filing (its
   `agent:ci-pipelines-maintainer` label is recorded on the verdict, never required: #3044 is open with
   the marker and zero labels), with its `**workflow:**` / `**run:**` fields parsed back — and classifies each with the SAME rule `scripts/ci_monitor.py` uses after
   #3048 — `classify_main_runs()` over that workflow's completed runs on `main`, ordered by
   `(updatedAt, databaseId)`.
2. One verdict line per issue: `SWEEP issue=<n> workflow=<name> run=<id> superseded-by <run>` when
   that workflow's newest completed main run is no longer red, `SWEEP … live newest-red=<run>` when it
   still is. A workflow with no completed main run since the filing is reported `no-newer-run`, never
   guessed.
3. `--apply` is the write half and it writes ONLY to issues it owns: a claim comment before acting
   (`scripts/bot_claims.py`), a closing comment naming the superseder run for a superseded issue, the
   current red run recorded for a live one. `--dry` (the default) prints verdicts and touches nothing.
4. `make monitor-triage-sweep` in `mk/bots.mk` wires the leg (host-only; `APPLY=1` opts into the
   writes), so the re-triage is a repeatable audited sweep and never a one-time manual pass.
5. Nothing in this change reruns, re-dispatches, cancels or merges a pipeline (AGENTS.md:
   queue-pumping is forbidden); the `gh` verbs are `issue list/view/comment/close` and
   `run list`/`run view` reads only, and a test pins that no mutation verb appears in the leg.

## Out of scope (each item is its own linked issue, named in the issue body)

- The PR half of the snapshot expanding one `PR-CHECKS` incident into every historical failed run on
  a head: #3047.
- Engine-bump PR bodies missing their OpenSpec change and acceptance checklist (#3050) and the
  pins-vs-image ordering (#3051).
