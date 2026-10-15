# Tasks

- [x] 1. `scripts/bot_sync_main.sh`: `reset` (fetch upstream main, hard-reset the tree) and `rebase` (fetch, rebase with `rerere` off), failing loudly when main is unreachable, exiting 2 on a conflict with the branch left exactly as found
- [x] 2. Makefile: `bot-sync-main` and `bot-sync-branch` (documented help text, in `.PHONY`)
- [x] 3. `.github/workflows/issue-bot.yml`: `make bot-sync-main` after checkout, so the branch the implementer pushes starts from latest main
- [x] 4. `.github/workflows/fix-bot.yml`: `make bot-sync-branch` before the repair loop, treating exit 2 as "leave it to the rebase-bot", and a `--force-with-lease` push afterwards
- [x] 5. `tests/test_bot_sync.py` (in `make test-unit`): a real scratch repository - branch on latest main, reset makes the tree exactly main, a conflicting branch is untouched and reported, an unreachable remote refuses to start, plus the wiring assertion for both workflows
- [x] 6. README: the "Bots sync with upstream main before they start work" section
- [x] 7. `agent-wiki/2026-10-15-bot-sync-before-work.md`: the work record
