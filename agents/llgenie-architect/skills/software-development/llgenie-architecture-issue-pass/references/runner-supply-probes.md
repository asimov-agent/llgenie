# Probing runner supply on a starved CI queue

Use when a matrix sits `queued` long enough that someone proposes a cause: "the label is not
provisionable on this plan", "the workflow is malformed", "the pool is just busy". Each of those
predicts the same observation — jobs with an empty `runner_name` — so observation alone cannot
separate them. A probe can, but only if it is built to.

## The rule: every probe carries a positive control in the SAME run

An experiment whose arms all fail does not distinguish **the hypothesis** from **the harness never
ran**. Three starving labels are consistent with "none of them can be provisioned" and equally with
"nothing was ever scheduled". Add one arm known to succeed (`ubuntu-latest`) to the identical run:

```
probe CONTROL ubuntu-latest | completed/SUCCESS | runner=GitHub Actions 1000044966 | 3s
probe macos-15-intel        | queued 7+ min      | runner=NONE
probe macos-14              | queued 7+ min      | runner=NONE
```

The control acquiring in seconds while both macOS arms stay queued is what makes the negative result
mean something. Without it the probe is a story, not a measurement.

## Build the probe without touching `main` or a real PR

1. `git worktree add -b probe/<topic> .worktrees/<name> origin/main`.
2. **Replace the `jobs:` block of an existing workflow** rather than adding a file — copy everything
   up to `\njobs:` verbatim so `on:`, `permissions:` and `concurrency:` are preserved, then write the
   probe jobs. Validate with a YAML parse and print `runs-on` per job before pushing.
3. Push, then `gh pr create` **ready-for-review, never `--draft`** (a draft is invisible to every reviewer
   scanning for work, and the fleet bans them) with a body that opens "**do not merge, do not review**"
   and states exactly what each arm distinguishes. Probes need a `pull_request` trigger, so the PR itself
   is part of the instrument — its title and body are what stop it being merged.
4. Make the probe jobs trivial (`uname -a`, `sw_vers`) with `timeout-minutes: 5`. The experiment is
   the label, not the workload.

### Two dispatch traps that look like "no runners"

- **404 `not found on the default branch`** — `gh workflow run <file> --ref <branch>` only works when
  that workflow file already exists on the DEFAULT branch. A file you just added on a scratch branch
  cannot be dispatched at all; modifying the `jobs:` of a workflow that is already on `main` can.
- **422 `Cannot trigger a 'workflow_dispatch' on a disabled workflow`** — a paused/disabled workflow is
  not dispatchable. If the fleet has paused automation workflows, dispatch is simply unavailable and a
  draft PR on a `pull_request` trigger is the way in. Do not re-enable a paused workflow to run a probe.

## Read the outcome, then the history

Per job: `status`, `conclusion`, `runner_name` (empty string, not null, while queued), `started_at`.

Then scan the repository's own history, because it answers "is this label EVER served here?" without
waiting on the queue:

```bash
gh api "repos/<owner>/<repo>/actions/runs?per_page=100" --jq '.workflow_runs[].id' | head -60 \
| while read r; do gh api repos/<owner>/<repo>/actions/runs/$r/jobs \
  --jq '.jobs[]|select(.name|test("macos";"i"))|"\(.conclusion//.status)\trunner=\(.runner_name//"NONE")"'; done \
| sort | uniq -c
```

Interpretation:

| pattern | conclusion |
|---|---|
| favourite label starves, control served | the resource, not the label name — swapping labels will not help |
| favourite label starves, a sibling label is served | label/plan provisioning; fix the label |
| control starves too | nothing is being scheduled; the harness or the account, not your workflow |
| history shows successes on that exact label in the same runner group | it is provisionable; report capacity, not provisioning |
| history shows `cancelled` with `runner=NONE` across the board | a queue that never issues runners; a mid-flight count proves nothing |

**Split the history by `runner_name`, not just by `conclusion`.** The decisive column is whether a job ever
HAD a runner: `cancelled` + `NO_RUNNER` (never started) and `cancelled` + `HAD_RUNNER` (started, then killed)
are different failures, and one of them can be misread as evidence against the starvation hypothesis. Report
the split with both numbers so a minority of `HAD_RUNNER` cases is visible as the exception it is:

```
cancelled  NO_RUNNER   65   ← the pattern
cancelled  HAD_RUNNER   2   ← the exception; state it rather than omitting it
success    HAD_RUNNER  11
```

## Clean up as part of the measurement

A probe left open costs the next lane a review. Close, delete, cancel, remove, and verify each one:

```bash
gh run cancel <run-id>; gh pr close <n> --delete-branch --comment "<result in one line>"
git worktree remove .worktrees/<name> --force   # may need sudo if root-owned
gh pr view <n> --json state --jq .state          # CLOSED
git ls-remote --heads origin probe/<topic> | wc -l   # 0
git worktree list | grep -c <name> || echo 0     # 0
```

Put the measured result in the close comment: the branch is ephemeral, the finding is not.
