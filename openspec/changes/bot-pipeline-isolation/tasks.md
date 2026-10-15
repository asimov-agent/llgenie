# Tasks

- [x] 1. Write the OpenSpec proposal + spec for per-bot pipeline isolation (issue #275, resolves #271/#272).
- [x] 2. Stagger the six bot crons so no two bots share a `(minute, weekday)` slot: engine-bump-rebase `17 5` -> `41 5`, engine-bump `23 6 * * 1` -> `53 6 * * 1`, registry-sync `17 5 * * 1` -> `19 5 * * 1`; keep issue-bot/fix-bot/queued-alarm unchanged.
- [x] 3. Add a `concurrency:` group (named after the bot, `cancel-in-progress: false`) to engine-bump, engine-bump-rebase and registry-sync; verify the other four already have one.
- [x] 4. `tests/test_bot_pipeline_isolation.py`: parse every scheduled workflow's cron and assert (a) no `(minute, weekday)` pair is owned by more than one bot, (b) no bot reuses a reserved hourly minute, (c) every bot has its own concurrency group with `cancel-in-progress: false`.
- [x] 5. Wire the test into `make test-unit` (add to the unit list), update README's bot pipeline section, add an `agent-wiki/` entry; run `make lint`, `make openspec-validate`, `make check-wiring`.
- [x] 6. Commit as one atomic change, push, open the PR against upstream main (closes #275).
