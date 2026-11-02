# The daily stale-branch cleanup retries a transient empty branch-list read (issue #1602)

Issue: [#1602](https://github.com/asimov-agent/llgenie/issues/1602). The daily
[stale-branch-cleanup](.github/workflows/stale-branch-cleanup.yml) run reads the repo's branch list
with `gh api --paginate --silent repos/{repo}/branches?per_page=100` through `_paged_json`. On a
TRANSIENT read fault — an rc=0 response with an empty stdout (the measured gh-CLI relay drop, run
41459018440), or an rc != 0 — the whole daily reds, and a daily that repeatedly reds on infra noise
teaches operators to ignore the red.

## What was verified

Measured at run 41459018440: `stale-branch cleanup FAILED — could not read the branch list:
\`gh api .../branches\` rc=0 stdout=''`. Re-verified live immediately after: the same endpoint returns
a populated list (length > 0) and `rate_limit.core.remaining` is healthy — a one-shot relay drop, not
a board state, not auth, not a rate cap. The acceptance path is fake-`gh` driven in
`tests/test_stale_branch_cleanup.py`:

- `test_transient_empty_branch_list_read_is_retried_and_recovers` plants a `gh` whose `branches?`
  read returns rc=0+empty once then valid, and asserts the sweep completes (exit 0).
- `test_persistent_empty_branch_list_read_still_reds` plants a `gh` that returns rc=0+empty on EVERY
  read and asserts it still exits non-zero and never prints `0 would be deleted` (#1514 intact).
- Both new tests FAIL when the retry is reverted (measured) — the prove-it-catches-a-bug step.

## Key decisions

- `_paged_json` loops the read with one bounded retry (2 attempts total): the FIRST transient fault
  is retried, and on the SECOND fault it raises `BranchListReadError`/returns `[]` exactly as before
  (issue #1514 discipline: a persistent read failure is never a clean board; a genuinely empty body
  — valid `[]` JSON — still exits 0).
- No API/CLI change, no workflow change, no guard weakened.

## Status

Script + tests + this note + the `docs/changes.d/` row land in one PR closing #1602.
`.github/workflows/stale-branch-cleanup.yml` is unchanged.
