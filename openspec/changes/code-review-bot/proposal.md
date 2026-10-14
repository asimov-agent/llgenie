# A code-review bot: read the tree and the pipelines, and file what is wrong

## Why

Every defect this repository caught in the last two days was caught by a human reading the tree:
`queued-alarm.yml` runs a repo script instead of a make target; two bots read a secret the repo does
not define; two cron pairs share a slot (05:17 and 06:23 UTC); `publish-agent-image.yml` had never
run once, and its first dispatch failed on a scope its own file claimed to handle.

None of those needed judgement to *find* — they needed someone to look. They are claims with a file
and a measured number behind them, which is exactly what a check can produce and a reviewer can
verify.

## What changes

- `scripts/code_review.py` — the deterministic core: `scan` (findings, writes nothing) and `file`
  (one issue per finding). No model anywhere in the path.
- `make code-review-scan` / `make code-review-file` — one make path per stage, the `REPO=`/`CAP=`/
  `DRY=` inputs documented in `make help` and the README.
- `.github/workflows/code-review-bot.yml` — guard first, then scan, then file; weekly (Monday 07:23
  UTC, its own slot) and `workflow_dispatch` for the owner/collaborators.
- Idempotence by marker: an issue carries `<!-- code-review:<key> -->`, the filer skips any key it
  has already filed, and a cap (3/run) bounds a bad run.
- `tests/test_code_review.py` — every check, the dedup, the cap, the argv, and the bot's own
  workflow against its own checks.

## What does NOT change

Nothing about how work is implemented. The bot is **analysis, never implementation** (AGENTS.md,
#231): it does not edit a file, open a PR, merge, or comment on anyone's PR — the tests assert that
its only `gh` verbs are `issue list` and `issue create`.

## Deliberate limits (measured, so they are honest rather than aspirational)

- `workflow-never-ran` skips `workflow_call`-only files: GitHub counts a reusable workflow's runs
  under its caller (`ci.yml` calls `pipeline.yml` three times, ci.yml reports 892 runs, pipeline.yml
  reports 0), so 0 there is an artefact. `reusable-orphan` is the check for those.
- `cron-collisions` only compares fixed minute+hour slots: an hourly cron fires many times a day by
  design, so it is not a collision.
- The two API-backed checks need a token with admin to read the secret list; without one they warn
  loudly and skip, rather than filing a claim they cannot support.
