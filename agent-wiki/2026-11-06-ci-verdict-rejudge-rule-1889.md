# #1889: durable fleet rule — re-judge a red ci-verdict via workflow_dispatch; expired job records trap a verdict

## What changed

Issue #1889 (from #1886) documents the durable fleet rule for re-judging a red `ci-verdict` and the
expiry trap that makes a verdict impossible to re-judge. The dispatch fix itself already exists on
`origin/main` (`ci-verdict.yml` gained a `workflow_dispatch` manual re-judge in #1886, merged
`4ef155c5`); this PR documents the behaviour — it changes no scripts, tests, or workflows.

## The canonical fleet bullet (added verbatim to every SOUL)

A red `ci-verdict` whose judged jobs are otherwise green is RE-JUDGED via the manual `workflow_dispatch`
(`.github/workflows/ci-verdict.yml`, `inputs.run_id` = the judged run, `inputs.head_sha` = its head),
never by re-running the whole judged CI fan-out. The dispatcher reads only that run's jobs + decision
and posts a fresh check-run; it edits no branch.

The **expiry trap**: a finished run whose job records have expired (`GET /actions/runs/{id}/jobs` →
`total_count` shredded to only the self row; measured run `42275871131` @ `cf88d285`, #1837, had only
its own row) can never be re-judged green — that verdict is trapped. An "N job(s) ABSENT" verdict is
the expiry symptom, not "the gate is broken"; the fix is a FRESH run at the head, not a re-judge of the
dead run.

## Files

- `agents/standing-rules.md` — one new canonical fleet bullet (the #873 single copy).
- every `agents/<profile>/SOUL.md` (13) — the same bullet inserted verbatim in each fleet section; the
  `fleet_block()` gate requires each non-exempt SOUL's stated block to equal the canonical verbatim,
  and `test_agent_profiles.py` pins a single byte-identical copy.
- pointer references carrying the two-point guidance in the ci-pipelines-maintainer, pr-rebase,
  reviewer, and planner-orchestration skills (`references/ci-verdict-rejudge-and-expiry.md`), wired
  into each SKILL.md.

## Gates

`make check-docs check-workflows check-wiring lint` stay green. `check-agent-profiles` fleet-block
portion green (pre-existing absent-from-tree items on other lanes are unrelated and unchanged).
