# A code-review bot: read the tree and the pipelines, and file what is wrong (#269)

## Why

Every defect this repository caught over the last two days was caught by a human reading the tree,
and each one was mechanical to detect once someone looked:

| what was found | evidence |
|---|---|
| `queued-alarm.yml` runs `python3 scripts/queued_run_alarm.py` directly, bypassing the rule that a workflow step calls a `make` target (and `make queued-alarm` exists) | its `run:` block |
| `issue-bot.yml` and `fix-bot.yml` read `secrets.NOUS_PORTAL_API_TOKEN`, which the repo does not define | job env shows `NOUS_API_KEY:` blank; the step stops at `NOUS_API_KEY unset - refusing to spend time on a dead key` |
| `engine-bump-rebase` (daily) and `registry-sync` (Monday) both fire at 05:17 UTC; `engine-bump` (Monday) and `issue-bot` (daily) both at 06:23 UTC | the `cron:` lines |
| `publish-agent-image.yml` had reported **0 runs ever**, and its first dispatch failed on a GHCR scope its own file claimed to handle | Actions API + the failed run |

None of those needed judgement to *find*, and each is a claim with a file and a measured number
behind it. That is what a check produces and a reviewer verifies — so the looking is now a bot's job.

## What was built

`scripts/code_review.py` (deterministic, stdlib only, `gh` through PATH), two make targets
(`code-review-scan`, `code-review-file`), a workflow (`.github/workflows/code-review-bot.yml`), an
OpenSpec change, README + this record, and `tests/test_code_review.py` (21 tests).

The contract is narrow on purpose, and the tests hold it to it: **issues and nothing else**. No file
edit, no branch, no PR, no comment on anyone's PR — asserted, not promised
(`test_the_bot_never_writes_code` pins its only `gh` verbs to `issue list` and `issue create`).

## The two limits that keep it honest

A checker that cries wolf gets ignored, so two checks were narrowed after measuring how the platform
actually behaves:

- **`workflow-never-ran` skips `workflow_call`-only files.** Measured: `ci.yml` invokes
  `pipeline.yml` three times, `ci.yml` reports 892 runs, and `pipeline.yml` reports **0** — GitHub
  counts a reusable workflow's runs under its caller. "0 runs" there is an artefact of the API, not
  evidence of neglect, so the check would have filed a false claim against two healthy pipelines.
  `reusable-orphan` is the check for those files instead (a `workflow_call` pipeline that nothing
  references).
- **`cron-collisions` compares only fixed minute+hour slots.** An hourly cron (the old refiner's
  `43 * * * *`) fires many times a day by design; reporting it as a collision would be noise.
- Plus: the documented gh/git orchestration exemption is honoured (`test_gh_orchestration_may_stay_shell`),
  and a token that cannot read the secret list causes a loud "SKIPPED this run" warning rather than a
  crash — a bot that dies on a permission it does not need files nothing.

## The first real run

`python3 scripts/code_review.py scan --repo asimov-agent/llgenie` found **4** findings on `main`, and
they were filed as issues by `make code-review-file` (the backlog the tree already had, now tracked):
the inline script in `queued-alarm.yml`, the undefined `NOUS_PORTAL_API_TOKEN`, and the two cron
collisions.

Self-consistency is part of the test suite: `test_the_bots_own_workflow_passes_the_bots_own_checks`
runs every check over the real repository and asserts that none of them names
`code-review-bot.yml` — the slot it picked (Monday 07:23 UTC) is its own, an hour after `engine-bump`.

## Verified

```
$ make code-review-scan REPO=asimov-agent/llgenie          # 4 findings, writes nothing
$ make code-review-file REPO=asimov-agent/llgenie DRY=1    # previews the issues, files nothing
$ uv run ... pytest tests/test_code_review.py              # 21 passed
$ make check-wiring && make lint                           # OK
```
