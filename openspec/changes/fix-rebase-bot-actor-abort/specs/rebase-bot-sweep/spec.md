# rebase-bot-sweep

## MODIFIED Requirements

### Requirement: a failed rebase leaves no stopped rebase behind

`scripts/rebase_bot.sh` MUST abort its own stopped rebase (`git rebase --abort`, a no-op when
nothing is in progress) on every failure path: the agent could not resolve the conflict,
`git rebase --continue` failed, or conflict markers remain. The tree MUST be left without
`rebase-merge`/`rebase-apply` state, so the caller's next `make` can parse `Makefile` — which a
failed conflict can itself have broken (issues #460/#462).

WHEN a rebase stops on a conflict in `Makefile` and the agent cannot resolve it
THEN the actor exits non-zero with a clean tree, and the drain loop's next decision runs normally.

#### Scenario: the actor leaves no stopped rebase behind
- **Given** a rebase that stops on a conflict and an agent that cannot resolve it
- **When** `scripts/rebase_bot.sh` exits non-zero
- **Then** no `rebase-merge`/`rebase-apply` state remains in the repository
- **Test:** `tests/test_rebase_bot_sweep.py::test_a_failing_agent_stops_the_run_without_pushing`
