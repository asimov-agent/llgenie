# `ci-verdict` names its judging job `judge`, not `verdict`, so GitHub's auto job check-run stops masquerading as the tip's verdict (issue #1871)

The `ci-verdict` workflow exists to hold a finished `CI` run to its scope decision (#1111):
a job the decision selected that is skipped/cancelled/absent, or a run with no decision, is a FAILED
verdict, and a `ci-verdict` check-run carries that answer to the head. #1864 moved the *posted*
`ci-verdict` check-run to the head it actually judged (the PR head, with its event/PR/branch named),
so a merged tip's own verdict is attributed correctly.

The residual #1871 tracks is the other row GitHub creates. A `workflow_run` workflow runs on the
DEFAULT branch, and GitHub auto-creates ONE check-run per job, named after the job's key and attached
to the head the workflow ran on. Before this change the job was named `verdict`, so a green `main`
tip showed BOTH the posted `ci-verdict: success` (the tip's own verdict) AND an auto `verdict` job
row that belonged to a judged PR — measured at `5bb742b2c2` on runs `42244374725` / `42244789060`,
which graded PR #1870's stale-base `fix/1849-pr-mc-log-read` branch (guard failed at
`make check-pr-base`). A reader on the tip could not tell the judged-PR red apart from a real tip
failure.

The fix renames the workflow's single job from `verdict` to `judge` (`.github/workflows/ci-verdict.yml`,
`jobs.judge`), so the workflow's GitHub-auto job row is `judge` and the only "verdict"-named row is
the posted, authoritative `ci-verdict` check-run. Verdict `make ci-verdict` logic in
`scripts/ci_verdict.py` and `scripts/ci_scope.py::verify()` is **untouched** — the no-decision red and
the skipped-selected-job red (#1862 AC-3) are byte-for-byte the same; only the workflow's internal
job key changed. The reactor (`run-failure-reactor`) routes on the workflow's top-level `name:`
(unchanged), so a red verdict is still consumed. The guard test
`tests/test_ci_verdict.py::test_the_judge_job_key_does_not_collide_with_the_authoritative_check_run_name`
proves the job key is `judge` and pins that GitHub's auto row can never again steal the `ci-verdict`
name (RED on the old `verdict` key, GREEN on `judge`).
