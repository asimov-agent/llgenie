# Drive a PR's CI to fully green — ownership, not a handoff

> Rule (owner directive 2026-11-04, escalated as a standing fleet rule): a PR is not
> "handed to CI" once — the lane that opens it owns its pipeline until **every** required
> gate is green at the **current head sha**. A mid-green PR (some gates green, one red,
> some still running) is a parked lane, not a done lane. The pr-reviewer reviews one
> head+sha; the ci-pipelines lane fixes pipeline defects; **neither** re-drives a partial
> PR to fully green unless it owns the PR. The owner is the implementer that opened it.

## Why this rule exists

A PR whose fix is correct but whose CI was never **re-evaluated** sits red forever:

- a** body-only edit (e.g. adding `closes #N`, fixing AGENTS/BASE) does NOT re-trigger
  CI and does not update an existing check-run — GitHub keys check-runs to the commit
  head SHA, so a body edit leaves the old pre-fix check in place. The live
  `guard`/`scope` block STILL evaluates the pre-fix body. Two consumers differ:
  `guard`/`scope` (check_pr_hygiene) read the body **live** via `gh api` (#1589), but
  pipeline.yml's `linux/unit` check-pr-closing reads `PR_BODY:
  ${{ github.event.pull_request.body || '' }}` — a **pipeline event snapshot** written to
  /tmp/pr-body.md at step start. So a body-only edit reliably greens guard/scope but the
  unit job's check-pr-closing stays **frozen on the pre-fix snapshot**, and even a plain
  job rerun re-uses the frozen body (#1711 filed to move pipeline to live read). The only
  way to re-snap a frozen body was to amend + force-push a NEW head (fresh pull_request
  event). Verify which consumer a gate is before declaring a body fix "landed". Fix = push
  a code change or re-dispatch the workflow (a genuine re-run at the current head), never
  merge around the stale block.
- a workflow that selects CI stages (ci-scope) runs `make check-docs` and can red on a
  real deficiency (undocumented make target / missing change-note / stale docs-exceptions
  entry) at the current head — re-running must happen until that gate actually passes.

## What "monitor until completely green" means in practice

1. The owning lane re-checks the PR's check-runs **after every push** and after every
   re-dispatch, at the CURRENT head sha (`gh api .../commits/<head>/check-runs`).
2. Every gate with `conclusion != success` at the head gets the lane's direct fix + a
   fresh run — not a one-line "will go green" hand wave and a back burner.
3. It is not "done" until all required gates report success on the head the merge queue
   will consume (send the head sha the green was measured at, never a stale older head).
4. If the blocker is the OWNER's domain (provisioning, a bigger runner), post the exact
   owner decision needed on the PR thread; otherwise the lane keeps driving.
5. Never assert green from memory or from an older head — the API at the current head is
   the fact (per references/ci-gate-vs-live-pipeline.md and verify-lane-claims).

## Who owns what

- implementer/owner of PR → drives its CI to fully green at the current head (this rule).
- pr-reviewer → reviews a head+sha once; still quotes a run id + sha, does not babysit.
- ci-pipelines-maintainer → fixes pipeline defects; also re-dispatches a gate it owns.
- planner → verifies every claim; if a PR sits mid-green with no lane driving it, that is
  an idle-capable lane: dispatch the drive-to-green explicitly or flag the gap.

Repeated correction (truncation of a stale claim, re-flagging the same gate) is never the
fix; the fix is a fresh run that re-evaluates the current head.

## Reproducing a failing gate locally (before you route it)

To name the *exact* deficiency a gate reds on, reproduce it against the PR's own head —
but two traps make a naive local run lie in both directions:

1. **Never run the gate against your primary clone.** It is routinely behind origin/main,
   so a `make check-docs` there reds on debt main already fixed (false positive) or passes
   on debt the PR carries (false negative). Extract the canonical tree first:
   `rm -rf /tmp/arch && mkdir /tmp/arch && git archive <head-sha> | tar -x -C /tmp/arch`,
   then run the gate inside `/tmp/arch`.
2. **A bare archive passes while CI reds** when the workflow injects env the gate reads
   only in CI — e.g. `make check-docs` skips its change→note check with no base ref
   (`[check-docs] note: change->note skipped (no base ref; set CHECK_DOCS_BASE)`) but the
   ci-scope job sets `CHECK_DOCS_BASE`, so it evaluates the diff there. Read the workflow
   YAML for the env the step sets and set the same vars, or accept that your local green
   does not prove the CI gate and let the owning lane re-dispatch at the head instead.

A repro you cannot make faithful is still useful: it partitions "stale-clone noise" from
"real PR defect" and tells you which lane owns the drive. It never substitutes for the
fresh CI run at the head that proves green.

## Read the failing job's own log before reproducing anything

Cheaper than a local repro, and it is the only thing that yields the cause line. Order:

1. **`gh pr checks <n>` prints an empty table** on this repo — it is not evidence of "no
   checks". List the head's check-runs instead:
   `gh api repos/$S/commits/<head>/check-runs --jq '.check_runs[]|"\(.name) \(.conclusion)"'`.
2. **Find the run + job id:** `gh run view <run-id> --repo $S --json status,conclusion,jobs`
   prints `status`, `conclusion` and each `job name/status/conclusion`. A run whose
   `guard` job is `success` while `scope` is `failure` is a real single-gate red — never
   upgrade "guard green" into "the workflow is green".
3. **The log:** `gh run view <run-id> --repo $S --job <job-id> --log > /tmp/job.log`
   (`--log-failed` for just the failed steps). This is the reliable reader.
   `gh api repos/$S/actions/jobs/<job-id>/logs` is the unreliable one: redirected to a
   file it can land 0 bytes, and it refuses output without `--allow-escape-sequences`.
   A 0-byte file is a wrong command, never "the log is unavailable" — re-read with
   `gh run view --job` before saying so.
4. **Annotations are not the cause.** `.../check-runs/<id>/annotations --jq '.[]|.message'`
   returns boilerplate (`Process completed with exit code 2.`, Node-20 deprecation). The
   cause lives in the job log, e.g.
   `[check-docs] ERROR: change->note: this branch changes <path> (+N more) but adds no agent-wiki/<stem>.md`.
   Quote that line, with the job id and head sha, in the dispatch — "scope is red" without
   the line is a verdict, not a diagnosis.

Two `gh` CLI traps while doing this: `gh api` has **no `--json` flag** (that flag belongs
only to `gh pr/issue/run view`) — use `--jq`; and query one field set per call rather than
concatenating several `--jq` outputs into one stream, which comes back unparseable.
