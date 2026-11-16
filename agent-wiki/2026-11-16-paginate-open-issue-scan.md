# Paginated open-issue scan for the pairwise dedupe bots (#2849)

Issue: #2849. OpenSpec change: paginate-open-issue-scan (spun out of #2848's `Not covered`;
fixes the #2847-measured blind window at open-list position 110/100 and the analogous 200-window
here).

## What was verified
- Root cause: `scripts/issue_dedup.py::candidates` and `scripts/issue_cleaner.py::open_issues` both
  scanned the open board with `gh issue list --state open --limit 200` — a single newest-first page
  capped at 200. As the board grows past 200 open issues, the OLDER half (where a duplicate pair's
  canonical, or the issue a merged PR implemented, lives) becomes invisible to the pairwise sweep.
  The same blindness just bit `registry_change_issue`'s 100-window at position 110 (#2659 / #2847).
- Fix: a shared `bot_claims.paginate_open_issues(gh_call, repo, per_page=100)` walks
  `gh api repos/{owner}/{repo}/issues?state=open&per_page=100&page=N` through the caller's `gh`
  transport seam until a SHORT page (< per_page), filters out pull requests (the `issues` endpoint
  returns them too), and normalises `createdAt` (from API `created_at`) so consumers read the same
  shape `gh issue list --json` produced. `issue_dedup.candidates` and `issue_cleaner.open_issues`
  route their scans through it, each via its own seam. No fixed window remains.
- Tests (both RED on the old `--limit 200`, GREEN on the paginated scan):
  `tests/test_issue_dedup.py::test_a_pair_straddling_the_old_200_boundary_is_still_found` (205 open
  issues, the similar pair's older member at open-list position 205 is still picked as canonical) and
  `tests/test_issue_cleaner.py::test_a_close_behind_open_list_position_200_is_still_seen` (205 open
  issues, the implemented issue at position 205 is still closed by its merged PR). The existing gh
  stubs in both modules now answer the paginated `gh api` call (slice by `page`/`per_page`).
- Gates: `tests/test_issue_dedup.py` + `tests/test_issue_cleaner.py` 36 passed rc=0; host run of the
  lint / check-workflows / check-wiring / check-docs / check-pr-hygiene gates all OK. `make test-unit`
  (host run of the discovered suite) = 3905 passed, 1 failed, 13203 deselected: the single failure is
  `tests/test_repo_slug.py::test_the_documented_invocations_carry_the_slug`, which is PRE-EXISTING and
  environmental — it fails identically on a clean tree (this container's `make -n` prints an
  "Entering directory '/repo'" cwd banner that the test asserts absent); it is unreachable from this
  change (no Makefile or `issue-cleaner-scan`/`queued-alarm` target was touched). The containerised
  gates and `make openspec-validate` run in CI with docker, unavailable in this agent container.

## Current status
Done on the agent's tree for issue #2849; tree left uncommitted for the job to commit and open the PR.
