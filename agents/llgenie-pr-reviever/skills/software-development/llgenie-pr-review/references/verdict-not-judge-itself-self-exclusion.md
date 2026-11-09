# A verdict job must not judge its own posted check-run (self-exclusion)

## Symptom

`ci-verdict` reds a fully-green CI run because GitHub attributes the check-run the `judge`
job ITSELF posts back into the judged run's job list (an 11th job named `ci-verdict`,
`workflow_name: CI`). `ci_scope.verify()` sees a job not in the decision table, concludes
`failure`, and counts it -> verdict=red. Once the check-run posts failure it stays in the list,
so EVERY re-judge re-counts it — a feedback loop no clean re-run breaks. Measured on run
42275871131 @ cf88d285 (#1882).

## Fix shape

Filter the row whose normalised job name == the verdict's OWN check-run name (CHECK_NAME)
from the observed set BEFORE `ci_scope.verify()` — the verdict is the report, not a gate.
Do not touch `ci_scope.py`/the decision table: a real selected job reporting failure must still
red. Normalise via `ci_scope.normalise_job_name` so a name/path mismatch doesn't bypass it.

## Verification (control pair on the SAME real run)
- Save the real run's job list (`gh api .../actions/runs/<id>/jobs > jobs.json`); assert the fix code
  and the pre-fix base both run against it. Fix: EXIT=0 verdict=green success=N failure=0 no
  `ci-verdict FAILED`. Base (git worktree at the pre-fix sha): EXIT=1 verdict=red `1 job(s)
  unaccounted for`. Same data, two outcomes — that is proof the change does work, not a no-op.
- CI container lacks `gh`/auth: run the verifier from the host repo venv where `gh` is in
  PATH; pass `--jobs jobs.json` so the job list is read from the saved file while the decision
  is still fetched live by run-id.

## Verdict-gated write-back

A PR whose closing issue has an unticked AC will red the guard with a precise message naming the
item and instructing `acceptance_writeback`. That is BY DESIGN (#1644): the reviewer provable-
threshold is the pick, the tick is the verdict. Tick via `--proven N`; the live-body
`check_pr_acceptance.py check` then returns rc=0. If the implementer already marked the AC
`## Not covered` with the PR itself (post-merge-only verification), leave it unticked — that is
honest, and the guard accepts a named-out-of-scope criterion.
