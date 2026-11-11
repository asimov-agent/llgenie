# Reference: trending-local-llms fix-bot (as measured)

Files: `.github/workflows/fix-bot.yml`, `.github/workflows/qa-validate.yml`
(`dispatch-fixbot` job), `scripts/fix_loop.sh`, Makefile `_fix` / `setup` /
`hermes-smoke` recipes, `tests/test_fix_loop.py`.

## Provider alias (Makefile `setup`)

```
hermes config set model.aliases.nous-deepseek.model deepseek/deepseek-v4-flash-0731
hermes config set model.aliases.nous-deepseek.provider custom
hermes config set model.aliases.nous-deepseek.base_url https://inference-api.nousresearch.com/v1
hermes config set model.aliases.nous-deepseek.key_env NOUS_API_KEY
hermes config set model.aliases.nous-deepseek.max_tokens 65536
hermes config set model.aliases.nous-deepseek.context_window 1048576
```

Budgets: `HERMES_REASONING := none` (search), `HERMES_FIX_REASONING := low` (fix).
The fix loop retries a round with `HERMES_FIX_REASONING=none` on the
budget-exhausted signature.

## The `_fix` prompt (essence)

The CI validation for the PR failed; the EXACT failures are in `qa-report.txt`
at the repo root — read it FIRST and fix those specific failures; do not guess.
Load AGENTS.md for acceptance criteria. (Then the concrete validator rules the
repo must satisfy.) Contract evolution: widen a contract only for real,
recurring data and update its tests in the same change; a breaking change gets
a new versioned contract file, old file untouched. Never invent a key/URL to
pass validation; if a link can't be verified, leave it and report it.

## Commit cap

`MAX_FIXBOT_COMMITS=2` in `qa-validate.yml`'s `dispatch-fixbot`; counting
`fix-bot:`-prefixed commits on the PR. At cap: "leaving PR for manual review."

## Why no `workflow_run`

Comment in `fix-bot.yml`: triggered ONLY by `workflow_dispatch` from
qa-validate; there is deliberately no `workflow_run` trigger. Push/PR made with
`GITHUB_TOKEN` do not trigger workflows, so the bot's own push would not re-run
CI and a `workflow_run` chain would not engage — explicit dispatch is used
instead. PR is created with the owner PAT so a `pull_request` run actually
starts.
