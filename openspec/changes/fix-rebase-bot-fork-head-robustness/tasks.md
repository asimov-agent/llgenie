# tasks — fix-rebase-bot-fork-head-robustness

- [x] 1.1 `scripts/rebase_bot.sh` fetches the PR head with a bounded retry that verifies the ref
- [x] 1.2 `scripts/rebase_bot.sh` verifies the checkout landed before rebasing
- [x] 1.3 the push-time dead-vehicle `gh pr view` is bounded-retried; persistent failure still refuses
- [x] 1.4 the fork-fetch-fault and transient-read tests exist and are green
- [x] 1.5 `pytest tests/test_rebase_bot_sweep.py` green
- [x] 1.6 `make openspec-validate NAME=fix-rebase-bot-fork-head-robustness` exits 0 and every task above is ticked
