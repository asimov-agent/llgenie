# fix-bot-retrigger

## ADDED Requirements

### Requirement: A failed CI run wakes the fix-bot for its own PR

The fix-bot SHALL be triggered by the `CI` workflow completing with `failure` for a `pull_request` run, SHALL
resolve that run's pull request, and SHALL dispatch the repair for exactly that PR. The hourly sweep SHALL
remain as a fallback that chooses the oldest eligible PR.

WHEN a pull_request CI run concludes `failure`
THEN the fix-bot resolves its PR and dispatches a repair for it, with the failed run's log as context.

#### Scenario: the sweep repairs the PR the failed run belongs to

Given two red same-repo PRs, the older one first by `updatedAt`
When  the sweep is pointed at the newer one (`--pr`)
Then  only that PR is dispatched, with `rounds=5`.

- **Test:** `tests/test_fix_bot_sweep.py::test_a_failed_run_repairs_its_own_pr_with_five_attempts`

#### Scenario: the workflow carries the trigger and the failure condition

Given `.github/workflows/fix-bot.yml`
When  its triggers and defaults are read
Then  it declares `workflow_run: workflows: ["CI"], types: [completed]`, acts only on
`conclusion == 'failure'`, and defaults to 5 rounds (`ATTEMPTS=5`).

- **Test:** `tests/test_fix_bot_sweep.py::test_a_workflow_run_trigger_is_wired_to_the_ci_workflow`

### Requirement: Up to five attempts, including a failure this runner cannot reproduce

The repair loop SHALL default to five attempts. When it is given the failed run's captured log
(`FIX_REPORT_FILE`), it SHALL repair from that log and report the result as UNVERIFIED — CI re-runs and
re-triggers the bot — rather than discarding the attempt because a local check cannot reproduce the failure.

WHEN the loop is given a captured failure log
THEN it makes one attempt from it, exits 0 with an UNVERIFIED marker, and the next CI failure re-triggers it.

#### Scenario: the captured log drives the attempt

Given a captured failure log for a check this runner cannot reproduce
When  the loop runs with `FIX_REPORT_FILE`
Then  it repairs from the log, exits 0, and prints `UNVERIFIED`.

- **Test:** `tests/test_fix_loop.py::test_a_captured_run_log_is_repaired_and_marked_unverified`

#### Scenario: the default is five attempts

Given a check that never goes green
When  the loop runs with no `FIX_ROUNDS`
Then  it makes five attempts, then gives up loudly for a human.

- **Test:** `tests/test_fix_loop.py::test_it_gives_up_loudly_after_five_rounds`

### Requirement: the provider preflight runs before the loop repairs anything

The `fix-loop-image` recipe SHALL run `scripts/agent_jev_preflight.sh` before `scripts/fix_loop.sh` in the
same command, so the provider key is wired into the agent home before the repair starts. The check that
locks this SHALL assert that ORDER, not the exact textual adjacency of the two commands: passing
`FIX_REPORT_FILE` into the loop (this change) legitimately puts an assignment between them, and a test that
pins the spelling reds both unit jobs while the behaviour is correct (PR #539, run 39921364286).

WHEN the `fix-loop-image` recipe is read
THEN it names both the preflight and the loop, and the preflight's position precedes the loop's.

#### Scenario: the preflight precedes the fix loop in the recipe

Given the `fix-loop-image` target in the `Makefile`
When  its recipe is read
Then  it passes the provider key by NAME, names `scripts/agent_jev_preflight.sh` before `scripts/fix_loop.sh`,
and a future argument added to either command does not fail the check.

- **Test:** `tests/test_agent_nerve.py::test_the_key_reaches_the_container_through_make_targets`
