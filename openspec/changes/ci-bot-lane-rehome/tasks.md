# Tasks: ci-bot-lane-rehome

- [x] 1. Keep six deactivated lanes (issue-bot, issue-dedupe, issue-refiner, architecture-bot,
      registry-sync-review, search-smoke): remove `on.schedule:` and add a header line stating who
      triggers the lane now.
- [x] 2. Retire rebase-bot: delete `rebase-bot.yml`, `scripts/rebase_bot.sh`,
      `scripts/rebase_bot_sweep.py`, their make targets, the `rebase-bot` name in `bots/pause.toml`,
      and the `rebase-bot` claim bot name while keeping the `rebase` work kind for
      `engine-bump-rebase`. The `.hermes/skills/rebase-conflict/` skill is KEPT as a HOST skill: it is
      the inner staging half `llgenie-pr-rebase` depends on, so it is admitted to `HOST_SKILLS`
      rather than deleted (issue #2703).
- [x] 3. Update shared consumers that name rebase-bot as a live lane (run_failure_reactor
      PIPELINE_STEMS, package-layers, AGENTS.md, docs/BOTS.md, README, tests) so no dotted
      reference to the retired bot remains.
- [x] 4. Write `tests/test_rebase_bot_retired.py` locking the dead-surface and the kept `rebase`
      work kind; it is discovered by the aggregated unit suite the moment it exists
      (`make test-unit`).
- [x] 5. Docs + index: agent-wiki note and CHANGES.md row naming issue #2703; README/docs section
      read cleanly without rebase-bot.
- [x] 6. Gates green: `make test-unit` (hermetic rebase/claims/workflow tests), `make lane-preflight`,
      `make check-wiring`.
