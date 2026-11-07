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
