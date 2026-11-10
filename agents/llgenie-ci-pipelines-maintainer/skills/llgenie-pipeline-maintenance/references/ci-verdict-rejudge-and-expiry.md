# Re-judging a red ci-verdict vs the expiry trap (fleet rule, #1889)

The canonical rule is the #1889 bullet in `agents/standing-rules.md` — this file is the operative
two-point pointer for this lane.

**1. A red `ci-verdict` whose judged jobs are otherwise green is RE-JUDGED, not re-run.** Dispatch
`.github/workflows/ci-verdict.yml` manually (`inputs.run_id` = the judged run, `inputs.head_sha` = its
head): the manual re-judge reads only that run's jobs + decision and posts a fresh check-run. It edits
no branch and never re-runs the judged CI. Re-running the full judged fan-out (guard, ci-images,
scanner-images, every linux job) just to regenerate job rows is the expensive, last-resort path — not
the default. The dispatch requires owner/collaborator permission; an agent that cannot dispatch must
route the re-judge call to the lane that can, not re-run the whole CI itself.

**2. The expiry trap: a finished run whose job records have EXPIRED can never be re-judged green.**
`GET /actions/runs/{id}/jobs` returns a shredded `total_count` once GitHub expires a finished run —
measured run `42275871131` @ `cf88d285` (#1837) had only its own `ci-verdict` row left, so the verdict
on that run was trapped at `red`/`none` on the head. A lane that sees an "N job(s) ABSENT" verdict must
read it as the expiry symptom, not "the gate is broken" and not "re-judge it again" — the fix is a
FRESH run at the head, because a dead run has no job records left to judge.

**3. "NO DECISION: this run published no scope decision" is usually an ORDERING fact, not a lost
artifact — read the judged run's guard job before theorising about the verdict.** On a red verdict, the
first question is whether the judged run published a decision at all: `GET /actions/runs/<id>/artifacts`
returning **empty** means it never uploaded one, which is the normal consequence of an earlier guard
failure, because `make check-pr-acceptance` runs INSIDE the guard job BEFORE the `ci-scope-decision`
upload step (`ci.yml`, acceptance ≈280, upload ≈325-335, same job). The acceptance gate exits 1, the
job dies, no artifact, `NO DECISION` → red verdict — the gate working. So the workflow is: read the
guard job's log for the failing step, name THAT gate as the cause, and route to its owner; do not open
a verdict-grammar fix. A verdict red is almost always a downstream report of a genuinely-red judged run.

**4. A PR that fixes the JUDGE cannot clear its own `ci-verdict` check — that is a bootstrap, not a
bug.** `ci-verdict.yml` checks out `ref: ${{ github.event.repository.default_branch }}`, so the judge
always runs MAIN's `scripts/ci_verdict.py` and `ci_scope.py`; a fix on a branch is inert until merge.
State the bootstrap in the PR rather than hunting a "gap in my fix", and verify the fix the only way
available — a local probe of the module (`verify(None, jobs)` against the measured job rows) plus tests,
with the wire verdict owed post-merge. Corollary for triage: a reactor-filed issue whose marker reads
`judge@<sha>` where `<sha>` is the default branch is naming the WRAPPER's head, not the judged run — the
judged run id is in the log's `RUN_ID:`. Confirm with `gh api .../actions/runs/<RUN_ID>` that it is a
`pull_request` run of some OPEN PR before calling it a main-tip red; those issues are duplicates of the
judged PR's own gate red, so attribute on the issue and on the PR, and cut no second vehicle.
