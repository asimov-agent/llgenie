# Tasks

- [x] 1. `scripts/issue_cleaner.py` reads `gh pr list --base main`, skips a PR whose `baseRefName` is not main, reports an idle-audit title as `audit`, and demotes a title-only issue named by several PRs to `vehicle`. Those two are not closed. An `Issue:` line and a single title-only PR still close. A `Not covered` remainder stays open.
- [x] 2. `.github/workflows/stale-branch-cleanup.yml` runs `make issue-cleaner-apply` from a `close-implemented` job on the existing daily cron and on workflow_dispatch. The step does not call the script. Branch deletion stays behind APPLY. The job holds `issues: write`.
- [x] 3. `tests/test_issue_cleaner.py` locks the off-main skip, the shared-title vehicle, the idle-audit title, the Issue-line close, and the workflow target.
- [x] 4. `docs/BOTS.md` and `docs/ARCHITECTURE.md` name the daily run. `agent-wiki/2026-11-01-close-implemented-on-stale-sweep-1414.md` and `docs/changes.d/2026-11-01-close-implemented-on-stale-sweep-1414.md` record it with #1414.
- [x] 5. `make openspec-validate NAME=close-implemented-on-stale-sweep`, the issue-cleaner unit tests, `make check-docs`, `make check-workflows` and `make check-wiring` exit 0.
