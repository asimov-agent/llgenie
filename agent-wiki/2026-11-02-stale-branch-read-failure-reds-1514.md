# The stale-branch cleanup reds on a branch-list read failure (issue #1514)

Issue: [#1514](https://github.com/asimov-agent/llgenie/issues/1514). The daily
[stale-branch-cleanup](.github/workflows/stale-branch-cleanup.yml) run reads the repo's branch list
with `gh api repos/{repo}/branches` through `_paged_json`. Before this change a failed read (auth
expiry, rate limit, network, 5xx) collapsed into `[]` — indistinguishable from "this repo has zero
branches" — so the report-only cron printed `report-only: 0 would be deleted` and exited 0: green,
while it deleted nothing it could not even see.

## What was verified

Measured at `main` `a5aff03b`: `_paged_json` (lines 41–45) returned `[]` on `rc != 0` or an empty
body, and `main` (line 120) discarded the rc. The acceptance path is fake-`gh` driven in
`tests/test_stale_branch_cleanup.py`:

- `test_faulted_branch_list_read_reds_even_in_report_only` plants a `gh` that exits 1 on every call
  and asserts the script exits non-zero and never prints `0 would be deleted`.
- `test_faulted_paged_json_raises_named_error` asserts `_paged_json` raises a named
  `BranchListReadError` on a non-zero rc, and still returns `[]` for a caller that passes
  `strict=False`.
- `test_genuinely_empty_branch_list_still_exits_0` proves the empty-board happy path is untouched:
  a repo with no branches still reports 0 and exits 0.
- Both fault tests FAIL when the fix is reverted (measured) — the prove-it-catches-a-bug step.

## Key decisions

- `_paged_json` gains a `strict=True` default that raises `BranchListReadError` (a named, catchable
  error) on a non-zero rc or an unreadable (empty / non-JSON) body. This is the only caller in the
  repo, so the stricter default touches nothing else.
- `main` catches it, prints a line naming the failed call and the branch count it never obtained, and
  returns 1 — so the report-only cron reds (and, per the run-failure-reactor roster, reaches a
  consumer) instead of reporting a clean sweep.
- The genuinely-empty path (a valid `[]` body) still exits 0; a real `[]` JSON body is not a fault.

## Status

Script + tests + this note land in one PR closing #1514. `.github/workflows/stale-branch-cleanup.yml`
is unchanged — the make target name/signature did not move.
