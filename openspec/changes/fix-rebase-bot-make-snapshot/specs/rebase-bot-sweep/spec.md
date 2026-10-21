# rebase-bot-sweep

## MODIFIED Requirements

### Requirement: the conflict agent is reachable while the tree is mid-rebase

`scripts/rebase_bot.sh` MUST take a snapshot of `Makefile` before it checks out the PR branch,
and its default agent command MUST invoke the agent through that snapshot
(`make -f <snapshot> rebase-bot-agent`). The `rebase-bot-agent` recipe MUST run Hermes directly
inside the agent image and MUST NOT invoke make inside the container, because the container's
`/repo/Makefile` is the conflicted file the agent is being asked to resolve.

WHEN a rebase stops with a conflict that includes `Makefile`
THEN the agent still starts, resolves the conflict, and the run continues to the gates and the
push.

#### Scenario: a conflict in Makefile does not stop the agent
- **Given** a PR whose rebase conflicts on `Makefile`
- **When** `scripts/rebase_bot.sh` hands the conflict to the agent
- **Then** it invokes `make -f <a snapshot taken before the checkout> rebase-bot-agent`
- **And** the recipe's container command is a direct `hermes` call, not `make`
- **Test:** `tests/test_rebase_bot_sweep.py::test_the_agent_is_invoked_through_a_pre_checkout_makefile_snapshot`

#### Scenario: the in-container make dependency is gone
- **Given** the Makefile's `rebase-bot-agent` target
- **When** its recipe is read
- **Then** it runs Hermes directly in the agent image and no `_rebase-bot-agent` target exists
- **Test:** `tests/test_rebase_bot_sweep.py::test_the_agent_recipe_runs_hermes_directly_inside_the_image`
