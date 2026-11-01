# close-implemented-on-stale-sweep — proposal

Issue: [#1414](https://github.com/asimov-agent/llgenie/issues/1414)

## Why

GitHub closes an issue only when the merged PR body carries an adjacent closing keyword. A PR titled
`(#N)` merges and leaves the issue open. `scripts/issue_cleaner.py` already decides that case
(`make issue-cleaner-apply`, issue #325) and no workflow runs it. The daily stale-branch cleanup
(issue #1344) retires the delivered branch while the issue stays open.

Measured on main `3c12b4de` with `--limit 60`: the unfiltered title rule would also close #1282
(idle-audit record #1377) and #1079 (tracking vehicle named by #1310 and #1319).

## What changes

- `.github/workflows/stale-branch-cleanup.yml` gains a `close-implemented` job that runs
  `make issue-cleaner-apply` on the existing daily cron and on `workflow_dispatch`. Branch deletion
  stays behind `APPLY`. The job calls the make target, not the script.
- `scripts/issue_cleaner.py` reads PRs merged into `main` only. A title-only match shared by several
  PRs in the scan is a tracking vehicle and stays open. An idle-audit title stays open. A `Not covered`
  remainder stays open. One merged-to-main PR that names one issue by `Issue: #N` or a single title
  still closes it.

## Not covered

- **#1413** — a single title-only slice that is not an idle-audit record can still close a tracking
  issue. That stricter signal is its own issue.
- **#843, #928, #964, #1006, #1010, #1015, #1079, #1245, #1282, #1365, #880** stay open. This change
  does not close them.
