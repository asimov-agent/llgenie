# Stale lane DM echoes, and reds that are structural gates

Two recurring traps when a lane's delivery or a CI red looks like news but is not.

## 1. A lane's repeated DM is a stale process echo, not a fresh report

Symptom: the same message re-delivers with the same pre-push head sha, a "live main" sha that is
two merges behind current main, and a phantom force-push attributed to the planner. The lane is
replaying a queued process, and its local refs (its own clone's `git rev-parse`, its own
`git ls-remote` against a mirror) can sit a whole merge-generation behind GitHub.

Settle it with the API, once:

- fork branch: `gh api repos/<owner>/<repo>/branches/<branch> --jq .commit.sha` — the API, never
the lane's `ls-remote`.
- PR: `gh api repos/<o>/<r>/pulls/<n> --jq '"head="+.head.sha+" base="+.base.sha[0:8]+" ms="+.mergeable_state'`
- drift: `gh api "repos/<o>/<r>/compare/<main>...<head>" --jq .behind_by` (0 = converged)

After the correct sha is posted on the issue AND read-back-verified, do NOT send a fourth or fifth
identical correction to the same lane — the durable issue record is the fix; re-sending teaches
nothing and burns turns.

The one harm-relevant check when a stale-echoing lane *claims* a no-op push/force-push is
safety-only: confirm fork ref and PR head still equal the last verified sha (a lane acting on a
stale belief could have clobbered the fork). If they match, there is no regression — close out.

## 2. A red `linux/unit` is not automatically a regression

On a PR whose openspec is legitimately mid-flight, `linux / unit` reds are often the **structural
unticked-boxes gate**, not code. Pull the job log and read the final `make ci-unit` failure:

    gh api repos/<o>/<r>/actions/jobs/<id>/logs --allow-escape-sequences
    gh api repos/<o>/<r>/actions/runs/<run>/jobs \
      --jq '.jobs[]|select(.id==<id>)|[.steps[]|select(.conclusion=="failure")|.name]'

If the only error is `[openspec-tasks] FAIL <change>: unchecked task checkbox(es) at lines [...]`
bubbling to `make[2]: *** [Makefile:...: openspec-tasks-check] Error 1` then `ci-unit Error 2`,
every substantive gate (unit tests, skills-validate, check-pr-base, check-pr-closing, authors,
lint, docs, census) PASSED and the red is only the openspec gate tripping on boxes that are
post-merge proof obligations. No re-run greens it until those boxes are ticked, so it does not
change owner-merge-readiness and is not a late regression — same class as a `scope` gate red or a
merge-tip unit red. Report the failing STEP name, the `openspec-tasks FAIL` line, the run id and
head sha, and state explicitly that the substantive gates passed.
