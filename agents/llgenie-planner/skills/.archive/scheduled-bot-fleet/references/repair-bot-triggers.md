# Repair-bot triggers: what wakes the bot, and how far it may go

A bot that repairs red PRs (a "fix bot") fails in a different way from a reporting bot: it can be perfectly
healthy and still never touch the PR the user is staring at. Three decisions decide that, and each has one
right answer.

## 1. The trigger: the failure itself, not the clock

A `schedule:` is a safety net, not a trigger. GitHub delivers scheduled workflows sparsely under load —
measured on an hourly cron (`17 * * * *`): ~9 deliveries in 36 hours, at ~4–5 hour gaps. A PR that goes red
in between waits hours, and the failed CI run — itself a `workflow_run` nobody consumes — is ignored.

```yaml
on:
  schedule:
    - cron: "17 * * * *"          # fallback sweep only
  workflow_run:
    workflows: ["CI"]
    types: [completed]
```

The job's condition is what keeps it narrow:

```yaml
    if: >-
      github.event_name == 'schedule' ||
      (github.event_name == 'workflow_run' &&
       github.event.workflow_run.event == 'pull_request' &&
       github.event.workflow_run.conclusion == 'failure')
```

A `workflow_run` executes the copy of the workflow on the **default branch** with the base repo's secrets, so
the trigger works for fork heads too. Expect the usual bootstrap: the PR that introduces the trigger is not
triggered by it.

## 2. The subject: the run's PR, not "the oldest eligible"

Resolve the PR from the run with the SAME resolver the merge gate uses (its 404/fallback/digits-only logic is
already tested; a second inline snippet is where the bugs live), then point the sweep at that PR explicitly:

```bash
make <bot>-resolve REPO=… RUN_ID=${{ github.event.workflow_run.id }} \
  HEAD_OWNER=${{ github.event.workflow_run.head_repository.owner.login }} \
  HEAD_BRANCH=${{ github.event.workflow_run.head_branch }}
make <bot>-sweep REPO=… PR="$PR" ATTEMPTS=5
```

A sweep without a `--pr`/`PR=` argument always answers "which PR is oldest", which is the wrong question when
a specific run just failed.

## 3. The context and the bound: the failed job's log, and a per-head counter

Capture the failed run's own log and hand it to the model instead of a fixed local check:

```bash
gh run view "$RUN_ID" --repo "$REPO" --log-failed > "$RUNNER_TEMP/failed.log" || true
```

Two rules for the loop:

- **A runner that cannot reproduce the failing job must still attempt the repair.** The classic loop runs its
  own check, hands the output to the model, re-checks, and pushes only on green. A macOS-only job, a
  GPU-only image test or a network flake is GREEN on the repair runner, so the loop pushes nothing and
  reports "still red" — having never read the log that names the failure. When the trigger supplies the run's
  log, seed the prompt with it, make ONE attempt, mark the result `UNVERIFIED`, push it, and let CI verify.
- **The attempt cap belongs to the HEAD, not to the run.** Count the bot's own commit prefix on the branch
  (`fix(bot):`) and stop at N (5 is a sane default). That is the only counter that survives across runs,
  which is what "re-triggered on the next failure" requires; an in-run `for` loop cannot express it.

State the outcome honestly in the PR comment: `repaired — check green`, or `UNVERIFIED attempt N/5, CI
re-runs to verify`. Never present an unverified attempt as a fix, and never let the loop's own green check
stand in for the check that actually failed.

## Diagnostics

- `gh run list --workflow <bot>.yml --limit 10 --json event,conclusion,createdAt` — the gap between
  `createdAt` values IS the trigger frequency; a "hourly" bot running 4-hourly is not reaching its subject.
- The workflow's `if:` is the second suspect: `github.event_name == 'schedule'` alone skips every
  `workflow_run`.
- `gh pr checks <n> --json name,state` versus the dispatched check: if the red job is not the one the loop
  runs, the loop cannot see it (see `SKILL.md`, the pass-over/check rules).
