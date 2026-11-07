# stale-branch-silent-suppresses

## Why

The daily `stale-branch-cleanup` cron has red 4 days straight (runs 41821928178, 42019350641,
42210560247, 42364955473). `scripts/stale_branch_cleanup.py::_paged_json` reads the branch list with
`gh api --paginate --silent <endpoint>`; `--silent` suppresses the response BODY (stdout), so the read
ALWAYS returns rc=0 with an empty body -> the one-bounded retry (#1602) retries the same suppressed
call -> `BranchListReadError` -> `make stale-branch-cleanup` exits 1 (Makefile:923). Measured at main
6940f9e7: `--silent` -> 0 bytes, without -> 15249 bytes.

## How

Drop `--silent` from `_paged_json`'s `gh api --paginate` call so the branch-list read returns the
populated body. The pre-existing test fake-`gh` stubs never modeled `--silent` (they print the body
regardless of the flag), so the bug shipped silently; add a regression test whose fake prints nothing
when `--silent` is present and the JSON otherwise, so it REDS on the old tree. Keep the one bounded
retry for genuine transient faults and the #1514 discipline (a persistently broken read, or a
genuinely empty `[]`, is still handled; a persistent fault is never a clean board).

## Benefits

- The daily run reads branches successfully again; report-only lists the real would-delete set with
  per-branch evidence (measured 55 would-delete / 12 kept at 6940f9e7).
- The safety predicate is untouched: a branch with an open PR, or with commits main lacks and no
  merged/closed PR, is REPORTED and never deleted.
- A stub now models the real CLI's body-suppression, so a future re-introduction of `--silent` is
  caught by CI instead of shipping as a 4-day red.
