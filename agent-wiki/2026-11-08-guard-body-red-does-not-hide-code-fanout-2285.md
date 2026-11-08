# guard body-red does not hide the code fan-out; ci-scope names the gate that blocked it (issue #2285) — 2026-11-08

**Implements:** issue #2285. `<repo>/docs/BOTS.md` promised "a red is measured, never silently skipped to
unmeasured" for the scope decision DATA; this change extends that to the JOB-level fan-out. A `guard`
job that fails on a PR-body text gate (`check-pr-acceptance-form` / `check-pr-acceptance`) carries a
non-zero exit, and GitHub's `needs:` default then auto-skips every dependent — so `linux / unit` +
`linux / openspec`, the ONLY code measurement a PR head gets, silently converted from "red" to
"unmeasured", and the ci-verdict judge reported `NO VERDICT: N job(s) unaccounted for — 0 failures is
not a verdict` against a run whose `guard FAILED` line sat three rows up.

## Root cause

Measured (run 42515444174, PR #2274; run 42510844644, PR #2279 ed08b376):

```
guard             failure   <- check-pr-acceptance-form / check-pr-acceptance red
ci-images         skipped   <- needs: [guard]
scanner-images    skipped   <- needs: [guard]
linux             skipped   <- needs: [ci-images, guard]
linux / lint      ABSENT      (no rows for any linux/* child)
...
summary: verdict=red success=0 failure=1 ... no-verdict=9
NO VERDICT: 10 job(s) unaccounted for — 0 failures is not a verdict   <- contradiction
```

The scope-decision publish step (#2156/#2248) already always-runs so a failing guard never erases the
DECISION; what was left is the job-level fan-out (`needs: [guard]` default skip) and the accounting
that could not attribute the ABSENT rows to the gate that prevented them.

## What changed

- **`.github/workflows/ci.yml` — the `linux` reusable call** now carries
  `if: ${{ always() && needs['ci-images'].result != 'failure' }}`: `always()` overrides GitHub's
  needs-default skip when the guard BODY-reds, so the code fan-out runs and is measured at that head;
  the `needs['ci-images']` half still stops it on a genuine image-build FAILURE, so a real red does
  not start an empty matrix. The guard body-red is unchanged — it still fails the run and blocks the
  merge.
- **`ci.yml` — `top_tier_rows` input** gains `|| '["none"]'`: a failed guard propagates no outputs,
  so the top-tier axis falls back to the PR-safe placeholder and the call still starts on a guard
  body-red (green guardian is byte-identical).
- **`scripts/ci_scope.py::verify()`** — a row the decision selected that is ABSENT or non-success
  while its gate (`guard`, or the `linux` caller for a `linux/*` child) is observed non-success is
  now counted `blocked` and its line names the gate (`blocked by linux skipped` / `blocked by guard
  failure`). A RED verdict names its failing job(s) (`RED: N FAILED (guard); M blocked by a gate`);
  a NONE verdict (zero failures) keeps the #1111 sentence, where zero is the point.

## Proven

Negative control (the exact measured shape, `verify()` on run 42515444174's rows):

- OLD: `verdict=red failure=1 no-verdict=9` + `NO VERDICT: 10 job(s) unaccounted for — 0 failures is
  not a verdict`.
- NEW: `verdict=red failure=1 blocked=9 no-verdict=0` + `RED: 1 job(s) FAILED (guard); 9 blocked by
  a gate; 0 unaccounted; 0 pending`, every blocked row naming its gate.

The workflow half is guarded by `tests/test_ci_images.py` (the exact `if:` is allowlisted as the one
needs-override that RUNS a guard-gated call, never a skip — the `no_ci_step_or_job_is_skipped` family
still forbids a skip condition) and `tests/test_ci_slow_rows.py` (the `with.top_tier_rows` fallback).
The accounting half by `tests/test_ci_verdict.py` (blocked classification, gate naming, the
caller-block attribution, the clean-gate honest no-verdict, and the named-RED sentence). 102 tests
green across the three suites; `make openspec-validate` green; `make check-workflows` green.

Not #2279: #2279 (open PR) closes #2061 — the ci_scope summary-sentence wording only. This change is
the #2285 job-level fan-out + gate-naming accounting; it shares the ci_scope sentence block because a
guard-red must not print the "0 failures" line, but its vehicle reason is the hidden matrix, not the
wording.
