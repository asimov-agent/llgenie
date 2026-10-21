# rebase-bot-sweep

## MODIFIED Requirements

### Requirement: the sweep decides from a COMPUTED merge state, never from an uncomputed one

`scripts/rebase_bot_sweep.py` MUST pick the one PR whose `mergeStateStatus` is `BEHIND` or
`DIRTY`. When GitHub reports a PR's state as `UNKNOWN` (mergeability not computed yet), the sweep
MUST re-query that PR through `gh pr view <n> --json mergeStateStatus`, bounded by
`UNKNOWN_ATTEMPTS` and `UNKNOWN_DELAY_S`, and use the resolved state. A PR that is still
`UNKNOWN` after the bound MUST be reported as deferred in `reasons` (naming the number and the
next-run retry) and in a `deferred` list on the result, and MUST NOT be described as not needing
a rebase.

WHEN the open-PR list reports `UNKNOWN` for a PR that is in fact conflicting with `main`
THEN the sweep re-asks that PR, resolves `DIRTY`, and takes it for rebase.

#### Scenario: an UNKNOWN PR that resolves to DIRTY is taken
- **Given** an open PR the list reports as `UNKNOWN`, whose `pr view` reports `DIRTY`
- **When** the sweep runs
- **Then** it picks that PR and reports `state=DIRTY`
- **Test:** `tests/test_rebase_bot_sweep.py::test_an_unknown_state_is_re_resolved_and_the_pr_is_taken`

#### Scenario: a PR that stays UNKNOWN is deferred by name
- **Given** an open PR whose `pr view` keeps reporting `UNKNOWN`
- **When** the sweep runs
- **Then** it picks nothing, names that PR as deferred, and says the next run retries
- **Test:** `tests/test_rebase_bot_sweep.py::test_a_pr_that_stays_unknown_is_deferred_not_ignored`

### Requirement: the rebase step can write its outcome comment

`.github/workflows/rebase-bot.yml`'s `Rebase it …` step MUST export `GH_TOKEN` (the job's own
`github.token`) so `scripts/rebase_bot.sh` can post its outcome comment and the `done` marker the
sweep's daily record and the other bots' claim readers depend on. A rebase with no marker is
invisible to both.

WHEN the actor finishes a rebase
THEN the step it runs in has `GH_TOKEN`, so `gh pr comment` succeeds and the marker lands.

#### Scenario: the rebase step carries the token that posts the marker
- **Given** `.github/workflows/rebase-bot.yml`
- **When** the `Rebase it …` step is read
- **Then** its `env:` carries `GH_TOKEN`, and the script it runs posts the outcome comment
- **Test:** `tests/test_rebase_bot_sweep.py::test_the_rebase_step_exports_gh_token`
