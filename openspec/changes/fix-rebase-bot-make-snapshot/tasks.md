# tasks — fix-rebase-bot-make-snapshot

## 1. The actor

- [x] 1.1 `scripts/rebase_bot.sh` snapshots `Makefile` before the checkout and defaults the agent to `make -f <snapshot> rebase-bot-agent`

## 2. The recipe

- [x] 2.1 `rebase-bot-agent` runs `hermes -z "$(cat)" -m nous-deepseek …` directly in the image
- [x] 2.2 the dead `_rebase-bot-agent` target is removed

## 3. Tests

- [x] 3.1 the actor snapshots the Makefile and passes `-f`
- [x] 3.2 the recipe no longer invokes make inside the container, and `_rebase-bot-agent` is gone

## 4. Documentation

- [x] 4.1 README's rebase-bot section states the snapshot rule
- [x] 4.2 `agent-wiki/` entry referencing issue #460 and the PR

## 5. Verification

- [x] 5.1 `pytest tests/test_rebase_bot_sweep.py` green
- [x] 5.2 `make test-unit` green
- [x] 5.3 structural gates (`check-wiring`, `check-docs`, `check-workflows`, `check-pr-hygiene`, `check-pr-authors`, `lint`) green
- [x] 5.4 `make openspec-validate NAME=fix-rebase-bot-make-snapshot` exits 0 and every task above is ticked
