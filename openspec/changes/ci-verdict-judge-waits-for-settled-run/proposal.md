# ci-verdict-judge-waits-for-settled-run

## Why

`ci-verdict`'s `judge` can read a CI run **while it is still settling** and render a verdict that
is not the run's final state. The `workflow_run` event fires on `completed`, but GitHub does not
settle the run's own records at the same instant: on the race instances measured 2026-11-07 the
judge read a run whose `linux / unit` job was **mid-upload** — the jobs listing still carried
`status: in_progress` for it (no `conclusion` yet) even though the run was reported complete. The
judge then counted that job as `pending`/absent and posted `no_verdict` for a run that concluded
green moments later:

- `#1969`'s red (check-run `128400888804`, head `5ca1310`): the judge read run `42370873993`
  while its `linux / unit` was mid-upload; the unit later concluded. The verdict on that head
  redded a run whose real rows were not all terminal yet.
- `#2010` (the run-fixer tracker this change closes) is the live instance of the same class: the
  judge failed against a head while the run's own job rows were not all `completed`.

The same race is the reason the old `#1990`/`#1998` pass was insufficient: that PR fixed only the
run-fixer *dedupe marker* (a quoted workflow name stopped one head+step being deduped, so every
failing run filed a fresh issue); it did not touch what the judge reads. The judge does not
"wait for/verify the decision artifact (and the run's jobs list) before producing a verdict", so a
verdict produced from a settling snapshot is a false red.

## What changes

`scripts/ci_verdict.py` gains a **settle gate** on the run-id path: before `ci_scope.verify()` is
allowed to count a job as `pending`/absent (which is what makes a mid-upload row a false `no
verdict`), the judge verifies the feeding snapshot is terminal:

1. After reading the run's jobs list, it checks every job row reports `status: completed` —
   a visible `in_progress`/`queued` row means the snapshot was taken mid-flight, and that is
   **never** a verdict: the judge refuses the read, reports the unsettled job, and exits `2`
   ("could not reach a verdict"), which the workflow surfaces as its own failure — never a
   posted `ci-verdict: failure` on the head for a run that is not done.
2. The decision artifact read (`decision_of`) is unchanged in behaviour — a missing artifact
   stays a legitimate `none` input for a genuinely cancelled run — but the jobs-list settle check
   runs first, so the artifact (uploaded by `guard`, the first job) is read only once it is final.

The `ci-verdict.yml` judge step needs no retry/`sleep` shell loop — the decision logic lives in
the tested script, not in a job-level `if:` (that shape is what `test_no_ci_step_or_job_is_skipped`
forbids). The gate is one testable function in `scripts/ci_verdict.py` plus the tests that prove
it refuses a mid-upload snapshot and still allows a settled one.

## Out of scope

- Any change to what the decision selects or to `ci_scope.verify()`'s accounting of real jobs.
- The run-fixer dedupe half of the `#1990` class (a quoted workflow name in the marker) — already
  landed in `#1998`.
- Any change to the `#2010` issue body; this change closes it from the implementing PR.
- A retry that keeps re-reading until the run settles *after* the step (no indefinite wait; a
  mid-flight snapshot is one error, routed to the normal run-fixer path).
