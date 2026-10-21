# issue-bot

## MODIFIED Requirements

### Requirement: the implement leg has its own budget, and its work is salvaged

`.github/workflows/issue-bot.yml`'s implement step MUST declare its own `timeout-minutes`,
strictly smaller than the job's, so the leg ends by name while time remains. The steps that detect
the change and commit+push the branch MUST run with `always()` so a timed-out or failed
implementation still publishes what the agent wrote. A step MUST name the outcome as a budget with
the tree state, branch and push result.

WHEN the implementation exceeds its budget
THEN the run fails with "Implementation budget: …", and any change is committed, pushed and
opened as a PR instead of being discarded with the runner.

#### Scenario: the leg's budget is below the job's
- **Given** `.github/workflows/issue-bot.yml`
- **When** the implement job and its impl step are read
- **Then** the step declares `timeout-minutes` (at least the bot floor) and it is smaller than the job's
- **Test:** `tests/test_bot_time_budget.py::test_the_implement_step_has_a_budget_below_the_job`

#### Scenario: a timed-out implementation still salvages
- **Given** the same workflow
- **When** the detect and push steps' conditions are read
- **Then** both carry `always()`
- **Test:** `tests/test_bot_time_budget.py::test_a_timed_out_implementation_still_salvages_the_tree`

#### Scenario: the budget failure is named
- **Given** the same workflow
- **When** the step keyed on `impl.outcome` is read
- **Then** its message names the budget and what survived (tree, branch, pushed)
- **Test:** `tests/test_bot_time_budget.py::test_the_budget_failure_is_named`
