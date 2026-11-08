# guard-body-red-does-not-hide-code-fanout

## Why

A guard job that fails on a PR-BODY text gate (`check-pr-acceptance-form`, `check-pr-acceptance`,
the sibling body-hygiene steps, issue #2285) carries a non-zero exit, and GitHub's `needs:` default
then auto-skips every dependent. In `ci.yml` all three depend on `guard` (`ci-images`,
`scanner-images`, and the `linux` call), so a body red silently converts the ONLY code
measurement a PR head gets (`linux / unit` + `linux / openspec`) from "red" into "unmeasured" —
measured on run 42510844644 (PR #2279 head ed08b376) and 42515444174 (PR #2274): `guard failure`,
then `ci-images skipped`, `scanner-images skipped`, `linux skipped`, and every `linux/*` child
absent. The ci-verdict judge then reports `NO VERDICT: N job(s) unaccounted for — 0 failures is not
a verdict` against a run whose `guard FAILED` line is printed three rows up: 10 jobs unaccounted
with a real failure named.

The scope-decision publish step (#2156/#2248) already proved the repo intent — "a guard that reds
on the PR body must not erase the following measurement" — for the DECISION data. This change
extends that principle to the JOB-level fan-out: the code fan-out runs even when the guard
body-reds, and the accounting names the gate that prevented a row instead of reporting an
anonymous ABSENT.

## What Changes

- `.github/workflows/ci.yml`: the `linux` reusable call gets `if: ${{ always() &&
  needs['ci-images'].result != 'failure' }}` so a guard body-red (`needs['guard']` failure) no
  longer auto-skips it — the code fan-out runs and is measured at that head. A genuine
  `ci-images` FAILURE still stops it (the other half of the condition), so a real image-build red
  does not start the fan-out for nothing. The guard body-red itself is unchanged: it still fails
  the run and blocks the merge.
- `ci.yml`: `top_tier_rows` input gains `|| '["none"]'` — a failed guard propagates no outputs to
  dependents, so the top-tier axis falls back to the PR-safe placeholder and the call still starts.
- `scripts/ci_scope.py::verify()`: a row that is ABSENT or non-success while its GATE (the `linux`
  caller for a `linux/*` child, else `guard`) is observed non-success is counted `blocked` and its
  line names the gate (`blocked by linux skipped` / `blocked by guard failure`), instead of an
  anonymous `no_verdict` / `NO VERDICT` sentence. A RED verdict names its failing job(s) and the
  blocked count; a NONE verdict (zero failures) keeps the #1111 `0 failures is not a verdict`
  wording, where zero is the point.

## Impact

- **who**: every author of a PR whose only red is a body-text gate (they regain a code verdict);
  every reader of a `ci-verdict` summary (the cause is named, never hidden).
- **what**: a guard body-red keeps the code fan-out green/red-measured at that head; a blocked
  matrix row names the gate that prevented it; a RED verdict states `N FAILED (guard); M blocked`.
- **regression surface**: the `if:` and fallback are pinned by `tests/test_ci_images.py` and
  `tests/test_ci_slow_rows.py`; the accounting by `tests/test_ci_verdict.py`; the check-workflows /
  no-skipped-job gates still forbid a silent skip condition.
