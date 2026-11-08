# `ci-verdict` stops redding a green head on its own rows and a cancelled auto-merge (issue #2221)

Measured at main `07a7db2a` on 2026-11-08: CI run `42460411318` = `success`, all 10 judged jobs
green; the ci-verdict run `42461521651` printed `verdict=green success=10 failure=0` and STILL posted
`conclusion=failure` (check-run `128671762099`, title `ci-verdict: green (run 42460411318)`). A board
reader saw the word `green` beside a red row and trusted it; the judged run was misreported red. This
is the defect behind #2221: `unjudged_reds` counted five blocking rows at the head that are NOT
external reds.

## Why the head is not broken even though the rows block

Two creator classes were being miscounted as "unjudged reds" (`scripts/auto_merge.py` refuses a merge
on any blocking conclusion, #1386, so the verdict rightfully hedges when a real external red exists —
#2116):

- **The verdict's OWN workflow rows.** `ci-verdict.yml` is a `workflow_run` workflow, so it runs on
  the default branch and GitHub auto-creates one check-run per job there, named after the JOB KEY
  (#1871): `judge` and `guard` rows sit on every `main` head. A prior verdict run's red leaves them
  `failure`; the next verdict — which judges only `ci.yml` — re-counts those `judge` failures as
  unjudged reds. That is a feedback loop: once red, every re-judge re-counts the judge rows it itself
  left behind. The existing CHECK_NAME skip only saw the *posted* row (named `ci-verdict`), never the
  auto job rows.
- **A cancelled auto-merge `merge` row.** auto-merge cancels its own superseded sweeps repo-wide
  (`cancel-in-progress: true`, #917), so on a busy `main` head a `merge=cancelled` row means "a newer
  sweep took over", never "the tree is broken". Only `cancelled` is the churn; a real
  `merge=failure`, `timed_out` or `neutral` stays an unjudged red.

## What changed

- `scripts/ci_verdict.py::unjudged_reds` now resolves each blocking row to its workflow FILE (the
  identity `workflow_of` already returns) and skips rows whose file is the verdict's OWN
  `.github/workflows/ci-verdict.yml` (taken from `verdict_roster.VERDICT_WORKFLOW`, so a rename cannot
  silently drift), then skips rows from `.github/workflows/auto-merge.yml` whose conclusion is
  `cancelled`. All other blocking rows are still named, exactly as before.
- The posted check-run's `output.title` is derived from the POSTED conclusion, never from the judged
  verdict word: `green` only when the conclusion is `success`, `failure`/`neutral` otherwise. A failed
  or superseded head can never read `ci-verdict: green`.
- `.github/workflows/ci-verdict.yml` documents the two exclusions where the UNJUDGED REDS block
  already explained the #2116 rule.

## Evidence

- Guard-proven both ways: with the code change stashed, the five new regression tests fail against the
  old tree with the exact measured symptoms (own `judge` rows counted, `merge=cancelled` counted, and
  the title reading `ci-verdict: green (replay)` beside `conclusion=failure`); with the fix they pass.
  The one negative control — a real auto-merge `merge=failure` still reds the verdict — passes before
  and after, so the gate is never weakened.
- Live specimen: `make ci-verdict REPO=asimov-agent/llgenie RUN_ID=42460411318` now prints
  `verdict=green success=10 failure=0`, emits no `UNJUDGED RED` line, and writes
  `conclusion=success` (rc 0). (The head had since moved, so the live run also reported the SUPERSEDED
  line for a newer CI run — the point stands: it no longer posts failure for a green judged run.)
- `tests/test_ci_verdict.py` 55 passed; related suites (`test_ci_scope`, `test_auto_merge`,
  `test_workflows_valid`, `test_ci_concurrency`, `test_verdict_roster`, `test_workflow_guards`,
  `test_arm_auto_merge`) 199 passed.

Delivered as a reviewable PR on branch `feat/ci-verdict-exclude-own-workflow-rows`
(base `origin/main@07a7db2a`), ready for the #1088 owner gate.
