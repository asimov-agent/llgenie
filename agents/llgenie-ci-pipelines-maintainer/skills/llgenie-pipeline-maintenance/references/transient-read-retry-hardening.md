# A transient read-fault retry is hardening, not gate weakening (#1602/#1603)

Measured 2026-11-02 on #1602/#1603 (squash `75b3d1b` on main).

## The decision

The stale-branch-cleanup daily reds whenever the branch-list read faults. The #1514/#453 discipline
(read failure is NEVER a clean board — a faulted `gh api .../branches` must not exit 0 reporting
"0 would be deleted") stays. The defect the planner surfaced was the OTHER side: a SINGLE TRANSIENT
fault (rc=0 with an empty stdout — the gh-CLI relay drop, run 41459018440, re-verified healthy
immediately after) reds the whole daily, and a daily that repeatedly reds on infra noise teaches
operators to ignore the red.

## The fix (one bounded retry)

- `_paged_json` loops the `gh api --paginate --silent .../branches` read with 2 attempts total.
  A first fault (rc != 0 OR rc=0-with-empty-stdout OR non-JSON body) is retried once.
- The SECOND fault still raises `BranchListReadError` (strict) / returns `[]` (non-strict) exactly
  as before. So a persistent broken read is still never a clean board; a genuinely empty list
  (valid `[]` JSON) still exits 0.
- Guard-prove BOTH directions against the OLD single-attempt code: the transient test FAILS without
  the retry (proves the retry is what allows recovery); the persistent-red test passes on both
  (proves the guard is not weakened).

## Cross-process fake-gh gotcha

A fake `gh` on PATH is spawned fresh per `_gh` call, so in-test state does NOT carry between the two
attempts. Use a counter FILE in the fake's bin dir (read at each subprocess start), not an in-script
variable, to make the first call return empty and the second valid. Also emit branch JSON via
`print(BRANCHES123)` where `BRANCHES123` is defined with `repr(json.dumps(...))` — a plain Python
list literal interpolated into the script prints single-quoted repr (invalid JSON for `json.loads`).

## Delivery

- Finding issue and fix PR separate (#1602 finding, #1603 fix); PR `closes #1602`;
  `agent-wiki/<stem>.md` note + `docs/changes.d/<stem>.md` ONE well-formed table row (mirror an
  existing working row: `| date | prose | [note](agent-wiki/...md) | #N |`) + `make changes-index`.
- The fresh branch is cut from live `upstream/main`; auto-merge may catch it fast after linux/unit
  (a main that advances quickly can red `check-pr-base` mid-queue — see the #1592 lesson).
- Verify the squash is an ancestor of main and run the decisive suite against a pristine archive of
  the merged tree before declaring done.
