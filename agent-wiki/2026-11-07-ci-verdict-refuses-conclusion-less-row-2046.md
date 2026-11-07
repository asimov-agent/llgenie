# ci-verdict: refuse a `completed` job row whose conclusion has not landed (#2046)

## Measured defect

The settle gate merged for `#2010`/`#2017` (`scripts/ci_verdict.py::require_settled`) refused a
run snapshot whose job rows were mid-upload by checking `status != "completed"`. But that is only
half of the race. GitHub's jobs API writes a finishing row's `status` field before its `conclusion`
field, so a row that reads `status: completed` with a still-empty `conclusion` is a run still
settling through the conclusion field. The gate let that row through: `ci_scope.verify()` counted
it `pending`, and the judge posted a false RED verdict (`conclusion=failure` check-run, exit 1) for
a run whose conclusion had not landed yet.

`#2046` is the tracked instance of the class: `ci-verdict`'s `judge` job reddened on a verdict
reached from a run that was still finishing its own rows — the false-red slice that `#2017`'s
status-only check could not see.

## Fix

`scripts/ci_verdict.py::require_settled()` now treats a row as settled only when BOTH

- `status == "completed"`, AND
- `conclusion` is non-empty.

A row with a completed `status` and an empty/missing `conclusion` is refused exactly like an
`in_progress` row: the job is named, `RuntimeError` routes through the existing error path to
`exit 2` ("could not reach a verdict"), and NO check-run is written — "no verdict" out loud, never
a red verdict from a snapshot the run has not finished writing.

## Guard-prove (negative control)

New test `test_a_completed_row_without_a_conclusion_is_refused_not_a_red_verdict` drives a decided
run whose `linux / unit` row reads `{"status":"completed","conclusion":null}`:

- on the PRE-fix tree the CLI exits **1** and writes a `conclusion=failure` check-run — the false
  red this change kills;
- on the FIXED tree it exits **2**, names `linux / unit` as not settled, and writes NO check-run —
  the negative control, proven twice (RED on the old predicate, green on the new).

The existing settle tests stay green: a genuinely settled red run still exits 1 naming the failing
gate, and a settled cancelled `none` (no artifact) still exits 1. `tests/test_ci_verdict.py` +
`tests/test_ci_scope.py` = 83 passed.

Implementing PR closes #2046. The check-pr-acceptance write-back on `#1696`/`#2039`/`#2043`/`#2049`
and `#2050` are out of the dispatch's scope (reviewer lane owns them).
