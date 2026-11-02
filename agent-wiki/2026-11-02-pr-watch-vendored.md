# 2026-11-02 pr_watch monitor vendored in-tree (issue #1577, closes #1037)

The PR-watch monitor `agents/llgenie-pr-reviever/scripts/pr_watch.py` (and its test module
`test_pr_watch.py`) landed in the repo, byte-identical to the live profile's copy. #1037's
null-run-id crash fix (`usable_run_id` reject-null, jq `select(.id != null)`, the not-usable
guard returning a stable "no CI run" line, and `except (Exception, SystemExit)` catching the
`gh()` abort that a bare `except Exception` missed) was previously verified live-only; this
worktree vendors it so the monitor — the lane's cron `monitor` script — is versioned,
diffable and reviewed under the #791/#1062 contract instead of being silently lost on profile
rebuild. Acceptance measured: the in-tree copy's sha256 equals the live script's
(`969ff473…`, 27,422 B), the diff is empty, `check-proc-gate` does not cover `agents/*/scripts/`
(verified surface: repo `scripts/` only), `check-empty-files` OK, and the naming note now lives
in the lane SKILL.md "Scheduled watch" section so the next reader checks the repo copy.