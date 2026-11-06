# Re-judging a red ci-verdict vs the expiry trap (fleet rule, #1889)

The canonical rule is the #1889 bullet in `agents/standing-rules.md` — this file is the operative
two-point pointer for the orchestrator lane.

**1. A red `ci-verdict` whose judged jobs are otherwise green is RE-JUDGED, not re-run.** Dispatch
`.github/workflows/ci-verdict.yml` manually (`inputs.run_id` = the judged run, `inputs.head_sha` = its
head): the manual re-judge reads only that run's jobs + decision and posts a fresh check-run. It edits
no branch and never re-runs the judged CI. A dispatch requires owner/collaborator permission; a lane
without it routes the re-judge call to an owner, it never re-runs the whole fan-out as a substitute.
When orchestrating a lane whose verdict is red for a retroactive reason, the re-judge dispatch is the
first-class answer and the other lane's "run it again and wait" reads as a stall, not a fix.

**2. The expiry trap: a finished run whose job records have EXPIRED can never be re-judged green.**
`GET /actions/runs/{id}/jobs` returns a shredded `total_count` once GitHub expires a finished run —
measured run `42275871131` @ `cf88d285` (#1837) had only its own `ci-verdict` row left, so the verdict
on that head was trapped at `red`/`none`. An "N job(s) ABSENT" verdict is the expiry symptom, not
"the gate is broken": route the lane to a FRESH run at the head rather than a re-judge of the dead run,
because the dead run has no job records left to judge.
