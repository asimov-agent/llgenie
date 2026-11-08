# ci-verdict-refuses-conclusion-less-row

## Why

`require_settled()` (merged in `#2017` for `#2010`) refuses a run snapshot whose job rows are
mid-upload — but it checks only `status`. A row that reports `status: completed` with an empty
`conclusion` is the other half of the same race: GitHub's job API writes a finishing row's `status`
before its `conclusion`, so the `completed` + `conclusion: null` shape is a run still settling.

That row passes `require_settled()`, is then counted `pending` by `ci_scope.verify()`, and the judge
posts a RED verdict (exit 1, `conclusion=failure` check-run) for a run whose conclusion has not
landed yet — the exact false red `#2017` set out to kill, reachable through the conclusion field
instead of the status field. `#2046` is the tracked failure of this class: the `judge` job turned a
net-red on a verdict reached from a row the run had not finished writing.

## What changes

`scripts/ci_verdict.py::require_settled()` treats a job row as settled only when BOTH its `status`
is `completed` AND its `conclusion` is non-empty. A row with a completed status and no conclusion is
refused like an `in_progress` row: the job is named, the exit is 2, and no check-run is written —
"no verdict" out loud, never a red verdict from an unsettled snapshot.

The `ci_scope.verify()` accounting is untouched: a genuinely settled `cancelled`/`skipped` row still
has a conclusion (e.g. `skipped`) and passes; a row with a genuinely empty conclusion on a settled
run is refused before any conclusion is reached.

## Out of scope

- The `run=` slot of the bot-verdict marker (`#2035`/`#2039`, reviewer lane owns that) — the dispatch
  of `#2046` names it out of scope; this change is `scripts/ci_verdict.py` only.
- Any change to `ci_scope.verify()` or what the decision selects.
- The check-pr-acceptance write-back (`#1696`/`#2039`/`#2043`/`#2049`) and `#2050` — explicitly out
  of the dispatch's scope.
