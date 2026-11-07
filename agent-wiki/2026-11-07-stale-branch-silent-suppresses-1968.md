# The daily stale-branch cleanup reds on a body-suppressed branch-list read (issue #1968)

Issue: [#1968](https://github.com/asimov-agent/llgenie/issues/1968). The daily
[stale-branch-cleanup](.github/workflows/stale-branch-cleanup.yml) 03:39 UTC run has redded 4 days
straight (runs 41821928178, 42019350641, 42210560247, 42364955473). The root cause is the branch-list
read itself, not a transient relay fault.

## What was verified

`scripts/stale_branch_cleanup.py::_paged_json` builds the branch-list `gh api` call with `--silent`
(added in the original #1361 pipeline and never noticed because the test fake-`gh` stubs never modeled
it). Measured against the real API at main 6940f9e7 this pass:

- `gh api --paginate --silent repos/asimov-agent/llgenie/branches?per_page=100` → rc=0, stdout=0 bytes.
- the same call WITHOUT `--silent` → rc=0, stdout=15249 bytes (the populated branch list).

`gh api --silent` suppresses the response BODY (stdout) — exactly the data `_paged_json` needs — on
every run, so the read always collapses to the empty body, the one-bounded retry (issue #1602) retries
the same suppressed call, and `BranchListReadError` reds `make stale-branch-cleanup` (Makefile:923).
The #1602 "transient empty-stdout class" and its retry were treating this persistent suppression as a
one-shot relay drop; the retry is preserved for genuine transient faults.

The fix drops `--silent` from the branch-list read (the only `_paged_json` caller). Report-only mode
against the real API now lists the would-delete set with per-branch evidence (measured live, 55
would-delete / 12 kept at main 6940f9e7), and the safety predicate is unchanged: a branch with an open
PR, or with commits main lacks and no merged/closed PR, is REPORTED and never deleted.

## Key decisions

- Drop `--silent` in `_paged_json` only; keep the one bounded retry for genuine transient faults and
  the #1514 discipline that a persistently broken read is never a clean board (a genuinely empty
  `[]` list still exits 0).
- New regression test `test_branch_list_read_does_not_suppress_body_with_silent` (`tests/test_stale_branch_cleanup.py`)
  models REAL `gh` behaviour — a `--silent` call prints nothing, a non-silent call prints the JSON —
  and FAILS on the old tree (guard-proven this pass), unlike the pre-existing stubs that print the body
  regardless of the flag and therefore never caught the suppression.
- No workflow change, no guard weakened, APPLY stays off.

## Status

Script + test + this note + the `docs/changes.d/` row land in one PR closing #1968.
`.github/workflows/stale-branch-cleanup.yml` is unchanged.
