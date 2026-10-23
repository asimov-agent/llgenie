# The fix-bot is woken by the failure it repairs

## Why

The fix-bot is the fleet's only automated repair path, and it could not repair the PRs that needed it:

- **Not re-triggered by a failure.** Its only automatic trigger was `schedule: 17 * * * *`, and GitHub
  delivered roughly 9 runs in 36 hours (`39884199020` 01:28Z, `39863859921` 22:17Z, `39832031405` 18:30Z,
  `39789658057` 13:45Z, `39741077226` 07:31Z, …). A PR that went red between two sweeps waited hours, and the
  failed `CI` run — a `workflow_run` nobody consumed — was ignored.
- **Three attempts, and never an unverified one.** `scripts/fix_loop.sh` ran `make ci-unit` locally, handed its
  output to the agent, re-checked, and exited 1 if still red; the workflow then pushed nothing. For a failure
  this runner cannot reproduce (`macos / unit` on PR #533 at 04:36Z, while `linux / unit` was green) the loop
  could never verify a fix, so it did nothing.
- **Always `make ci-unit`.** The sweep dispatched `CHECK="make ci-unit"` whatever job failed.

## What Changes

- **`workflow_run` on `CI`**: `fix-bot.yml` now wakes when a `pull_request` CI run concludes `failure`, resolves
  that run's PR with `make auto-merge-resolve` (the tested resolver the merge gate uses), and dispatches the
  repair for THAT PR. The hourly sweep stays as a safety net.
- **Five attempts** everywhere: the sweep's `--max-attempts` default, the workflow's `rounds` default, and
  `fix_loop.sh`'s default are 5. The attempt counter is still the PR's `fix(bot):` commits, so a head receives
  at most 5 bot attempts and then stops, saying so on the PR.
- **The failed run's log is the repair context**: the job captures `gh run view <id> --log-failed` and passes it
  as `FIX_REPORT_FILE`; the loop repairs from it, marks the result **UNVERIFIED**, and lets CI verify and
  re-trigger — instead of discarding the attempt because a local check it cannot reproduce is green.
- **`--pr N`** on the sweep evaluates exactly the named PR, never "the oldest eligible".
- Tests pin all of it, including the workflow's trigger and the 5-attempt default.

## Impact

- A red PR is acted on within minutes of its failed run, on the PR that failed.
- A macOS-only or GPU-only failure is no longer outside the bot's reach; CI remains the verifier.
- The loop stays bounded: 5 attempts per head, then a comment and a human.
