# bot-schedules

## ADDED Requirements

### Requirement: A scheduled bot fires at an odd minute

Every `cron:` minute in every workflow SHALL be odd, so no bot is scheduled on a top-of-hour or half-hour slot
that GitHub drops under load (`queued-alarm.yml` already records this: *"an odd minute; GitHub drops
top-of-hour runs"*, #275/#301). The guard SHALL derive its scope from the workflow files, never from a
hand-kept list, so a bot added tomorrow is inside it.

WHEN a workflow declares a `schedule:` whose minute field expands to any even minute
THEN `make test-unit` fails, naming the workflow and the minute.

#### Scenario: an even cron minute is refused

Given a workflow file whose cron expands to the minutes `0` and `30`
When  the isolation guard reads the workflow directory
Then  it fails and names that workflow and minute 0.

- **Test:** `tests/test_bot_pipeline_isolation.py::test_every_cron_minute_is_odd`

#### Scenario: every cron in the tree passes

Given the workflows on disk, where every cron minute is odd
When  the isolation guard runs
Then  it passes and the cron set it read is not empty.

- **Test:** `tests/test_bot_pipeline_isolation.py::test_every_cron_minute_is_odd`

### Requirement: The auto-merge sweep stays scheduled

`auto-merge.yml` SHALL keep a `schedule:` trigger for its `recheck` sweep, at a 30-minute cadence on odd
minutes. The always()-on-CI-completion retry added by #559 SHALL NOT replace it: a deferral can clear with no
push at all, and only a scheduled run retries that.

WHEN `auto-merge.yml` is read
THEN it declares a `recheck` job, a schedule, and that schedule's minutes are odd.

#### Scenario: the sweep's cron is odd and periodic

Given `.github/workflows/auto-merge.yml`
When  its schedule is expanded
Then  it fires twice an hour, on odd minutes, and its `recheck` job still calls `make auto-merge-recheck`.

- **Test:** `tests/test_bot_pipeline_isolation.py::test_the_auto_merge_sweep_stays_scheduled`

#### Scenario: dropping the schedule fails

Given `auto-merge.yml` with its `schedule:` block removed
When  the guard runs
Then  it fails, because the CI-completion retry alone cannot retry a deferral that clears without a push.

- **Test:** `tests/test_bot_pipeline_isolation.py::test_the_auto_merge_sweep_stays_scheduled`
