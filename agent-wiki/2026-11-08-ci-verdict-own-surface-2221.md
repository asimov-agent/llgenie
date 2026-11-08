# ci-verdict stops redding a green main head on its own rows and on other workflows' transients (issue #2221) — 2026-11-08

**Implements:** issue #2221 — a `main` tip that was genuinely green read RED on `ci-verdict`. At
`main` `07a7db2a` (the merge commit of #2161), CI run `42460411318` was `push`, `conclusion.success`,
all 10 judged jobs green — the verdict printed `verdict=green success=10 failure=0` and still posted
`conclusion=failure` (check-run `128671762099`, titled `ci-verdict: green (run 42460411318)`). The
title and the conclusion contradicted each other on the same row.

## Root cause

`scripts/ci_verdict.py::unjudged_reds` (added for #2116) refuses to call a head clean while a red
check-run from a workflow it did not judge sits on it — but at a `main` head it counted rows that are
NOT judgement gaps:

1. **The verdict's OWN `judge` job rows.** A `workflow_run` posts its job check-runs at the
   default-branch head every run (#1871), so this workflow's own rows always land on `main`. They were
   excluded only by row name (`CHECK_NAME`), not by workflow FILE, so a red `judge` auto-job (the
   verdict failing its own exit code) was counted as an "unjudged red" — a self-feedback loop: each red
   verdict fails the `judge` job and leaves a NEW `judge` row for the next verdict to count.
2. **`BLOCKING_CONCLUSIONS` includes `cancelled`/`neutral`**, and `auto-merge`'s `merge` job concludes
   `cancelled` when a newer sweep supersedes it (or a `main` push has nothing to merge) — a transient,
   not a defect, yet it redded a green head.

Measured on-wire: 5 rows counted (4 `judge` failure rows from runs `42461521651`/`42461576425`/… and
one `auto-merge merge=cancelled` from run `42461420528`).

## What changed

- **`scripts/ci_verdict.py`** — `unjudged_reds` now excludes the verdict's OWN workflow surface by
  FILE (`OUR_WORKFLOW_FILE = ci-verdict.yml`), not by row name, so the posted `CHECK_NAME` row and the
  `judge`/`guard` job auto-rows are never counted (fix 1). It blocks only on a genuinely-red unjudged
  conclusion (`UNJUDGED_RED_CONCLUSIONS = {failure, timed_out, startup_failure}`); a `cancelled`/
  `neutral` unjudged row is a superseded / owed-nothing transient and never reds a green judged head
  (fix 2). `BLOCKING_CONCLUSIONS` — the MERGER's #1386 rule, pinned equal to `auto_merge.RED_CONCLUSIONS`
  by `test_the_blocking_conclusions_are_the_merger_s_rule` — is deliberately unchanged.
- **`ci_scope.check_run_payload`** gains an optional `title` override; `ci_verdict.main()` computes the
  posted title from the EFFECTIVE conclusion, so a failure row is titled `ci-verdict: red`, never
  `ci-verdict: green` (fix 3 — the title/conclusion contradiction).
- **`tests/test_ci_verdict.py`** — five new/strengthened assertions covering the three behaviours:
  own-surface exclusion, the auto-merge cancelled-transient rule (+ a negative control proving a real
  unjudged `failure` still blocks), and the title/conclusion rule.

## Proof

- **Prove-guard:** each new test FAILS on the pre-fix `scripts/ci_verdict.py`/`ci_scope.py` (reverted
  scripts, re-ran the tests: the four bug-catching tests fail; only the negative-control
  `test_a_failure_from_an_unjudged_workflow_still_blocks` passes on old code, as intended) and PASSES
  on the fix.
- **Live reproduction of the issue's specimen:** `make ci-verdict REPO=asimov-agent/llgenie
  RUN_ID=42460411318 HEAD_SHA=07a7db2a34e00352fd9da32a4ebeaecccd73c219 CHECK_RUN_OUT=/tmp/v.json` at the
  branch head now exits **0**, reports `verdict=green success=10 failure=0`, posts `conclusion=success`
  (was `failure`); `unjudged_reds` returns `[]` (was 5 rows).
- **#2156 pagination intact:** `check_runs_of` still collects 192/192 unique rows at head `520db900`
  (no truncation raise).
- **Tests:** `tests/test_ci_verdict.py` + `tests/test_ci_scope.py` — 97 passed; `make verdict-roster`
  and `make check-wiring` green.
