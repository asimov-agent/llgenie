# Re-judging a red ci-verdict vs the expiry trap (fleet rule, #1889)

The canonical rule is the #1889 bullet in `agents/standing-rules.md` — this file is the operative
two-point pointer for this lane.

**1. A red `ci-verdict` whose judged jobs are otherwise green is RE-JUDGED, not re-run.** Dispatch
`.github/workflows/ci-verdict.yml` manually (`inputs.run_id` = the judged run, `inputs.head_sha` = its
head): the manual re-judge reads only that run's jobs + decision and posts a fresh check-run. It edits
no branch and never re-runs the judged CI. Re-running the full judged fan-out just to regenerate job
rows is the expensive, last-resort path — not the default. When a pending PR's verdict is red only for
a retroactive reason, this lane routes the re-judge (or verifies it) against the CURRENT head, never
reads a stale first-attempt verdict as current truth.

**2. The expiry trap: a finished run whose job records have EXPIRED can never be re-judged green.**
`GET /actions/runs/{id}/jobs` returns a shredded `total_count` once GitHub expires a finished run —
measured run `42275871131` @ `cf88d285` (#1837) had only its own `ci-verdict` row left, so the verdict
on that run was trapped. An "N job(s) ABSENT" verdict is the expiry symptom, not "the gate is broken":
a re-judge of the dead run will re-answer from the same shredded set, so the fix is a FRESH run at the
head and it is that fresh verdict this lane must review.
