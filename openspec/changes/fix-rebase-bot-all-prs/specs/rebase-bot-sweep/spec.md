# rebase-bot-sweep

## MODIFIED Requirements

### Requirement: one run rebases every eligible PR, bounded, and keeps going after a failure

`.github/workflows/rebase-bot.yml` MUST re-ask `make rebase-bot-sweep` after each rebase and act on
its answer, so one run drains every eligible PR instead of stopping after one. The number of
rebases per run MUST be bounded by the `max_prs` dispatch input (documented, default 10) and still
by the sweep's daily cap. When a picked PR's rebase fails, the run MUST abort it with `make
rebase-bot-abort` so the next decision runs on a clean tree, MUST count it, MUST continue with the
remaining PRs, and MUST exit non-zero at the end naming the failures.

WHEN several open PRs are `DIRTY` or `BEHIND` against `main`
THEN one run rebases all of them (oldest first) up to `max_prs`, and reports each failure without
abandoning the rest.

#### Scenario: the loop drains the backlog in one run
- **Given** the rebase workflow on `main`
- **When** its steps are read
- **Then** one step loops calling `make rebase-bot-sweep` and `make rebase-bot`, bounded by `MAX_PR`, and stops when the sweep no longer says `rebase`
- **And** the `max_prs` dispatch input is documented with a default
- **Test:** `tests/test_rebase_bot_sweep.py::test_the_run_drains_every_eligible_pr_up_to_the_bound`

#### Scenario: a failed rebase is aborted, counted and does not stop the rest
- **Given** the same loop
- **When** `make rebase-bot` fails for one PR
- **Then** the run calls `make rebase-bot-abort`, counts the failure, keeps iterating, and exits non-zero at the end
- **Test:** `tests/test_rebase_bot_sweep.py::test_a_failed_rebase_is_aborted_and_reported_without_stopping_the_loop`

#### Scenario: the abort target returns the tree to main
- **Given** the Makefile and README
- **When** `rebase-bot-abort` is read
- **Then** it aborts a stopped rebase and checks out `main`, and the target is documented and phony
- **Test:** `tests/test_rebase_bot_sweep.py::test_the_abort_target_resets_the_tree_to_main`
