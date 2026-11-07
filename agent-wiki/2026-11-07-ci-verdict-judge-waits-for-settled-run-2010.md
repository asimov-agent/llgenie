# ci-verdict: refuse a mid-upload run snapshot instead of judging it (#2010)

## Measured defect

A `workflow_run` event with `types: [completed]` can fire while the judged run's OWN records are
still settling. On the `#2010`/`#1969` class measured 2026-11-07, the judge read a run whose
`linux / unit` job was mid-upload — the jobs listing still carried `status: in_progress` for it
(no `conclusion`) even though the run was reported complete. The judge then produced a `verdict:
none`/`no_verdict` for a run that was going to conclude green moments later: `ci_scope.verify()`
saw the `in_progress` row as `pending`, `failure=0 no-verdict=1` was "not a verdict", and the head
carried a false `ci-verdict: failure` check-run.

The `#1998` pass (the run-fixer dedupe marker quote) did not touch the judge's read path, which is
why the class was still live post-merge.

## Fix

`scripts/ci_verdict.py` gains `require_settled(jobs)`, called in `main()` immediately after the
jobs list is read and before the decision artifact is trusted:

- any job row with `status != "completed"` (`in_progress`, `queued`) makes the listing a
  not-finished snapshot → `raise RuntimeError`, which the existing error path turns into
  `exit 2` ("could not reach a verdict") and NO posted check-run;
- the `ci-verdict.yml` judge surfaces that as its own unreachable-verdict failure (routed by the
  run-fixer), never as a verdict on the head;
- a fully settled run — including a genuine red and a genuinely cancelled `none` — is judged
  exactly as before; the gate never weakens a reached verdict.

A mid-upload run is one error, not a retry loop: the event fired once, so the judge reports the
run was not settled and the run-fixer routes it (the manual `workflow_dispatch` re-judge exists for
a run that is now settled). No retry/`sleep` lives in the workflow — the decision logic is in the
tested script, never a job-level `if:`.

## Guard-prove

New tests `test_a_mid_upload_job_row_is_refused_not_a_verdict` and
`test_a_mid_upload_row_is_an_error_never_a_pass_through_the_api` fail on the pre-fix tree (the
gate disabled: the mid-upload run is judged and posted) and pass with the gate on. The settled-red
and settled-`none` tests pin that a reached verdict is unchanged. `tests/test_ci_verdict.py` 38/38.

This fixes the `ci-verdict` judge side of the `#1990`/`#2010` class; the run-fixer dedupe half
already landed in `#1998`. Implementing PR closes #2010.
