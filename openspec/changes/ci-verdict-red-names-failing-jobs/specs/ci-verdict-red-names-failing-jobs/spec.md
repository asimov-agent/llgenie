# ci-verdict-red-names-failing-jobs Specification

## Purpose

Hold a finished CI run to its scope decision with a summary that states the
cause of a non-green verdict truthfully: a RED verdict names its failing
job(s), a NONE verdict keeps the #1111 "0 failures is not a verdict" sentence,
and a GREEN verdict adds nothing.

## Goals

- A red `ci-verdict` never prints "0 failures" beside an actual failure.
- The failing job is named (`1 FAILED (guard)`), not hidden behind a count.
- `verdict`, `counts`, and the process exit code are byte-identical between the
  old and new code paths for every shape.

## Non-Goals

- No change to which jobs are selected, how conclusions are normalised, or the
  exit-code / check-run posting contract.
- No change to `ci-verdict.yml`, `ci.yml`, or any security gate.

## Requirements

### REQ-1: A RED verdict names its failing jobs

Given a run whose own guard job FAILED and the selected rows skipped/absent
(no decision), when the verdict is computed, then the summary ends with a line
that contains `1 FAILED (guard)` and contains no `0 failures is not a verdict`
wording, and `verdict` is `red`.

### REQ-2: A NONE verdict keeps the #1111 sentence

Given a run with zero failures and absent/skipped rows and no decision, when
the verdict is computed, then the summary ends with the exact sentence
`NO VERDICT: N job(s) unaccounted for — 0 failures is not a verdict` and
`verdict` is `none`.

### REQ-3: A GREEN verdict is unchanged

Given a run for which every selected job reported success, when the verdict is
computed, then no final non-green sentence is added, `verdict` is `green`, and
`counts`/exit code are unchanged.
