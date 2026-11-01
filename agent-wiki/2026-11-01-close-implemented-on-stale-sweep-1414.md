# Close an implemented issue on the stale-branch cleanup run (issue #1414)

Issue: [#1414](https://github.com/asimov-agent/llgenie/issues/1414). The closer script landed for
[#325](https://github.com/asimov-agent/llgenie/issues/325). Its schedule did not. The branch pipeline
is [#1344](https://github.com/asimov-agent/llgenie/issues/1344).

## What was verified

`rg issue-cleaner .github/workflows` on main `3c12b4de` was empty. `make issue-cleaner-apply` existed
and nothing called it. A dry scan of the last 60 merged PRs (`--limit 60`) would have closed #1282
via #1377 (an idle-audit record) and #1079 via #1310 and #1319 (one tracking issue, two title-only PRs).

## Key decisions

- The schedule is a second job on `.github/workflows/stale-branch-cleanup.yml`, same cron `39 3 * * *`.
  No new workflow and no new closer. Branch deletion stays behind `APPLY`. The close runs on the cron
  and on `workflow_dispatch`.
- Only a PR merged into `main` counts. A merge into a stack branch does not close the issue.
- A title-only match shared by several PRs in the scan is a tracking vehicle and stays open.
- A title that is an idle-audit record stays open. An `Issue:` line on the merge commit still closes.
- A single title-only slice that is neither of those can still close the issue. That gap is #1413.

## Status

The ten issues whose implementing work was already on main were closed by hand, with a comment naming
the merged PR: #870, #1116, #948, #976, #988, #1031, #973, #968, #924, #844. #844 notes that #1029
removed the `install-published-*` jobs, so the original checklist was superseded rather than done as
written. #843, #928, #964, #1006, #1010, #1015, #1079, #1245, #1282, #1365 and #880 stay open.
