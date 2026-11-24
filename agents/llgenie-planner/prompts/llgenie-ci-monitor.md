# Prompt: llgenie-ci-monitor (Hermes cron job `857ee38c40ce`, profile `llgenie-planner`, every 30m; issues #3019, #3048)

The live cron job carries this text verbatim as its prompt; this file is its home in the repo so
the monitor agent behavior is reviewable and versioned. The job is monitor-gated: its
`--monitor-script` (`~/.hermes/profiles/llgenie-planner/scripts/llgenie_ci_monitor.py`, wrapping
`make -s ci-monitor`) is byte-stable, so the agent runs only when the incident snapshot changes.

Monitor tick for asimov-agent/llgenie CI. The injected snapshot lists incidents: MAIN-RED
(completed main runs that failed/cancelled/timed_out AND are still their workflow's newest completed
run on main), PR-CHECKS (open PR jobs not passing),
PR-MERGE (DIRTY/BEHIND), PR-REVIEW (CHANGES_REQUESTED), MONITOR-ERROR (monitor read failed), or
MONITOR-OK (board clean). A main red that a newer completed main run of the same workflow replaced is
NOT in the snapshot at all: it is history, not an incident, and only `INCLUDE_SUPERSEDED=1` prints it
as MAIN-SUPERSEDED lines for a human read - never treat those as work and never route them
(issue #3048). FIRST run `make ci-monitor-triage` in the repo workdir: scripted routing
files the failure issues (marker-deduped, TRIAGE-* verdict lines, dispatches nothing). Then act on
incidents ONE at a time per AGENTS.md: a red pipeline on a PR lane you own is fixed ON ITS BRANCH -
read gh run view --log-failed, root-cause, commit, push (pipeline/gate failures:
agent:ci-pipelines-maintainer; product code: agent:implement); rebase BEHIND/DIRTY PRs onto latest
origin/main; arm lanes green + CLEAN; never merge by hand, never rerun or dispatch pipelines to
clear a failure, leave draft PRs alone. While a pushed lane CI is in flight do NOT idle-poll it:
the wait lives only in a background watcher and your next action is the next open board issue
end-to-end (issue -> OpenSpec change first -> worktree off origin/main -> make gates -> PR whose
body closes it), one lane at a time. If MONITOR-OK and an open board issue has no PR yet and no
lane is active: take the oldest such issue the same way. A `MONITOR-ERROR clone-refresh-failed`
line means the monitor clone cannot refresh itself: treat it as an alarm, not a quiet board -
check `~/.hermes/checkouts/llgenie-main` (origin url, clean status, fetch) and restore the refresh
path; do NOT idle this tick (issue #3016). A `MONITOR-ERROR make-ci-monitor-failed` line means
"not landed" ONLY when the clone is current (its HEAD is origin/main); then do nothing this tick.
