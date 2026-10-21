# 2026-10-21 — the rebase bot's structural gate really gates the push (issue #455)

## What was wrong

Run `39553726935` showed `make lint` failing inside the actor (`pull access denied for
llgenie/test`) and the branch being pushed anyway, with a comment claiming the gates passed. The
gate command was a `;` list — the shell reports only the LAST command's status — and the runner
never has the test image `lint` runs in.

## What changed

- `scripts/rebase_bot.sh`: the default gates are chained with `&&`
  (`make -n ci-unit && make lint && make check-wiring`).
- `.github/workflows/rebase-bot.yml`: `make test-image` runs before the drain step, so `make lint`
  has the image it needs (pull-or-build, the repo's one entry for it).
- `tests/test_rebase_bot_sweep.py`: a failing gate blocks the push (real actor, real scratch
  repo), the default chain is `&&`, and the workflow provides the image before the drain step.

## Verified

- `pytest tests/test_rebase_bot_sweep.py` 37 passed.
- Full unit suite recorded in the PR.

## Status

Issue #455; PR #484 from `feat/rebase-bot-real-gates` against `asimov-agent/llgenie:main`. Waiting for
review — the agent never merges.
