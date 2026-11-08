# ci-verdict must not red a green head on ITS OWN workflow rows or a cancelled auto-merge

## Why

Measured at main `07a7db2a` (2026-11-08): CI run `42460411318` = `success`, all 10 judged jobs green;
ci-verdict run `42461521651` printed `verdict=green success=10 failure=0` and STILL posted
`conclusion=failure` (check-run `128671762099`, title `ci-verdict: green (run 42460411318)`).
`unjudged_reds` counted five blocking rows at the main head that are NOT the judged run:

- four `judge` job rows whose workflow FILE is `.github/workflows/ci-verdict.yml` — the verdict's OWN
  workflow. A `workflow_run` workflow auto-creates one check-run per job on the head it ran on (the
  default branch), named after the job key (#1871), so `ci-verdict.yml`'s own `judge`/`guard` rows sit
  on a main head. A previous verdict run's red leaves them `failure`, and the next verdict — which
  judges only `ci.yml` — counted them as EXTERNAL unjudged reds: a self-sustaining feedback loop.
- one `merge=cancelled` row (run `42461420528`) from `.github/workflows/auto-merge.yml`. auto-merge
  cancels its own superseded sweeps repo-wide (`cancel-in-progress: true`, #917); a cancelled `merge`
  row on a busy head says "the merger superseded itself", not "the tree is broken".

And the posted row's title said `green` while the conclusion was `failure` — the word a reader trusts
next to a red row (#2221). The title must say what the posted conclusion says.

## What changes

- `scripts/ci_verdict.py::unjudged_reds` excludes rows whose workflow FILE is the verdict's OWN
  `.github/workflows/ci-verdict.yml` (excluded by FILE, not by the `ci-verdict` check name — the auto
  job row is named `judge`, not `ci-verdict`, so the existing CHECK_NAME skip cannot see it).
- The same function exempts an auto-merge row whose conclusion is `cancelled` — a superseded sweep is
  churn, never a pipeline defect. Any other auto-merge blocking conclusion (a real `merge=failure`)
  STAYS an unjudged red, so the gate is never weakened.
- The posted check-run's `output.title` is derived from the POSTED conclusion, never from the judged
  verdict word: `green` only when the conclusion is `success`, so a failed/superseded head can never
  read `ci-verdict: green`.

## Who

llgenie-ci-pipelines-maintainer (this lane owns the pipelines and their guards).
