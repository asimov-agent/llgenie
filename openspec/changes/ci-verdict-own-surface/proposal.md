# ci-verdict stops redding a green main head on its own rows and on other workflows' transients

## Why

`scripts/ci_verdict.py::unjudged_reds` (added with #2116) refuses to call a head clean while a red
check-run from a workflow it did not judge sits on it. But at a `main` head it counted rows that are
NOT judgement gaps. Measured 2026-11-08 at `main` `07a7db2a` (CI run `42460411318`, `push`,
`conclusion.success`, all 10 judged jobs green): the verdict printed
`verdict=green success=10 failure=0` and STILL posted `conclusion=failure` (check-run `128671762099`,
titled `ci-verdict: green (run 42460411318)`). `unjudged_reds` returned 5 "blockers":

1. **four `judge` rows from the verdict's OWN workflow** (runs `42461521651` / `42461576425` and two
   more) — a `workflow_run` posts its job check-runs at the default-branch head every run (#1871), so
   this workflow's own rows always land on `main`; they were excluded by row name only
   (`CHECK_NAME`), not by workflow file.
2. **one `merge=cancelled` row from `auto-merge`** (run `42461420528`) — `BLOCKING_CONCLUSIONS` includes
   `cancelled`/`neutral`, and a cancelled auto-merge sweep (or a `main` push with nothing to merge) is
   a transient, not a defect.

The result is a self-feedback loop (each red verdict fails the `judge` job and leaves another `judge`
row) that makes `main` read red when nothing is wrong.

## What changes

1. `unjudged_reds` excludes the verdict's OWN workflow surface by FILE
   (`OUR_WORKFLOW_FILE = ci-verdict.yml`), not by row name — the posted `CHECK_NAME` row AND the
   `judge`/`guard` job auto-rows. A verdict never reds a head on its own footprint.
2. An unjudged row blocks only when its conclusion is a genuine red — `failure`/`timed_out`/
   `startup_failure` (`UNJUDGED_RED_CONCLUSIONS`). `cancelled`/`neutral` are superseded / owed-nothing
   transients and do not red a green judged head. `BLOCKING_CONCLUSIONS` (the merger's #1386 rule,
   pinned equal to `auto_merge.RED_CONCLUSIONS` by test) is deliberately unchanged.
3. The posted title names the EFFECTIVE verdict: a `conclusion=failure` row is titled `ci-verdict:
   red`, never `ci-verdict: green` (`ci_scope.check_run_payload` gains an optional `title` override).

## Change-first

GitHub issue #2221 is the single surviving tracker this implements; the branch
`fix/2221-ci-verdict-own-surface` carries the change; the PR closes #2221. The #2156 pagination fix is
left intact (`check_runs_of` untouched); judged CI is not re-run.
