# Re-home the deactivated CI bot lanes (issue #2703)

Classified the seven in-scope lanes #2701 deactivated (all but ci-requeue, its own #2702).

- Six kept dispatch/event-only: issue-bot (issues: labeled + workflow_dispatch), issue-dedupe,
  issue-refiner, architecture-bot, registry-sync-review, search-smoke (workflow_dispatch). Each
  workflow lost its `on.schedule:` block and gained a header line naming who triggers it now
  (a human or the interactive host agent).
- rebase-bot retired: deleted its workflow, scripts (rebase_bot.sh / rebase_bot_sweep.py), make
  targets, the rebase-conflict skill dir, the pause.toml entry, the claim name, and every dead
  reference in scripts / Makefile / engines.mk / bots.mk / AGENTS.md / docs / tests. Kept the
  `rebase` claim WORK KIND and `engine-bump-rebase` (exports bot_claims.ENGINE_BUMP).

Reference: issue #2703, PR #2704. Supersedes the cron-driven dispatch removed under #2701.
