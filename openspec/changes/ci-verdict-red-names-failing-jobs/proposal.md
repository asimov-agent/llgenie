# ci-verdict-red-names-failing-jobs

## Why

When a run's own `guard` job fails, every selected row is skipped or absent and
`counts["failure"] = 1`, yet `scripts/ci_scope.py::verify()` printed
`NO VERDICT: N job(s) unaccounted for — 0 failures is not a verdict` — the exact
#1111 sentence written for a run with *zero* failures, repeated beside a real
`guard FAILED` line. A board triager reading the check-run annotation saw "0
failures" for a red run whose guard had just reddened (issue #2061; measured on
run 42505814856 @ 1238c15e and on #2061's three runs 42428359272 /
42428362394 / 42428367776).

## What Changes

The non-green sentence is split by *why* the verdict is not green, in
`scripts/ci_scope.py::verify()`:

- `verdict = RED` (`counts["failure"] >= 1`) → the summary names the failing
  job(s): `RED: N job(s) unaccounted for — {failure} FAILED ({jobs}), {no_verdict}
  unaccounted, {pending} pending`. `verify()` now tracks the failing job names.
- `verdict = NONE` (zero failures, rows absent/skipped) → the #1111 wording is
  kept verbatim: `NO VERDICT: ... 0 failures is not a verdict`, where zero
  failures is exactly the point.
- `verdict = GREEN` → unchanged (no line).

`verdict`, `counts`, the exit code, and every normalisation/selection change are
untouched; this is a message-only change to the summary line.

## Impact

- **who**: every reader of a `ci-verdict` check-run summary.
- **what**: a red `ci-verdict` states the failure it measured (`1 FAILED
  (guard)`) instead of `0 failures`.
- **regression surface**: tests pin the new RED line, the unchanged NONE line,
  and the unchanged green case (byte-identical `verdict`/`counts`/exit code).
