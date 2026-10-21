# rebase-bot-sweep

## MODIFIED Requirements

### Requirement: eligibility is the merge state; today's marker only bounds the daily cap

`scripts/rebase_bot_sweep.py` MUST pass a PR over only when its resolved merge state does not need
a rebase, when it is a draft, targets another base, lives on a repo this bot cannot push to, has
checks in flight, or is in the `skip` list of PRs already rebased **by this run**. A PR carrying
today's `rebased` marker that is again `BEHIND`/`DIRTY` MUST be picked. The `rebased` markers MUST
still bound `MAX_PER_DAY`.

WHEN a PR was rebased this morning and a later merge made it stale again
THEN the same day's next run rebases it again, and one run never picks it twice.

#### Scenario: a re-dirtied PR is rebased again the same day
- **Given** a PR carrying today's `rebased` marker whose state is again `DIRTY`
- **When** the sweep runs
- **Then** it picks that PR and no "already rebased today" pass-over is recorded
- **Test:** `tests/test_rebase_bot_sweep.py::test_a_pr_rebased_today_that_main_re_dirtied_is_picked_again`

#### Scenario: one run does not repeat a PR
- **Given** two `DIRTY` PRs, with `skip=[7]` for the one this run already rebased
- **When** the sweep runs
- **Then** it picks the other PR and says #7 was already rebased in this run
- **Test:** `tests/test_rebase_bot_sweep.py::test_the_run_skips_the_prs_it_already_rebased_in_this_run`

#### Scenario: the loop forwards the PRs it handled
- **Given** the workflow's drain step
- **When** its script is read
- **Then** it starts with an empty skip list, passes `SKIP=` to the sweep, and appends every PR it handled — rebased or failed
- **Test:** `tests/test_rebase_bot_sweep.py::test_the_loop_passes_the_prs_it_already_did`
