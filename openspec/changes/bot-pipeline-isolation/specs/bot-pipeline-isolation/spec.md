# bot-pipeline-isolation

## ADDED Requirements

### Requirement: no two bots share a cron slot

Each bot workflow's schedule SHALL own a set of `(minute, weekday)` slots, and no
`(minute, weekday)` slot SHALL be owned by more than one bot workflow, so two bots never start
the same work at the same time. The hourly bots reserve their minutes (`fix-bot` :17,
`queued-alarm` :07 and :37) on every weekday, so no daily or weekly bot may reuse them.

#### Scenario: two daily bots never share a minute

- **GIVEN** the scheduled bot workflows in `.github/workflows/*.yml`,
- **WHEN** each bot's cron is expanded into its owned `(minute, weekday)` pairs,
- **THEN** no pair is owned by more than one bot.

- **Test:** `tests/test_bot_pipeline_isolation.py::test_no_workflow_shares_a_minute`

#### Scenario: a weekly bot does not collide with a daily bot on its weekday

- **GIVEN** `engine-bump` (Monday 06:53) and `issue-bot` (daily 06:23),
- **WHEN** both schedulers are read,
- **THEN** they never run at the same minute on any day.

- **Test:** `tests/test_bot_pipeline_isolation.py::test_no_workflow_shares_a_minute`

#### Scenario: a daily bot never reuses an hourly bot's minute

- **GIVEN** the hourly bots `fix-bot` (minute 17) and `queued-alarm` (minutes 07, 37),
- **WHEN** any daily or weekly bot's cron is read,
- **THEN** its minute SHALL NOT be 17, 7 or 37.

- **Test:** `tests/test_bot_pipeline_isolation.py::test_the_hourly_bots_minutes_are_not_reused`

### Requirement: every bot workflow has its own concurrency group

Every scheduled bot workflow SHALL declare a `concurrency:` group of its own with
`cancel-in-progress: false`, so a manual `workflow_dispatch` of a bot is queued behind its
scheduled run instead of running in parallel, and no two bots share a group.

#### Scenario: the three bots missing a group get one

- **GIVEN** the bot workflows `engine-bump`, `engine-bump-rebase` and `registry-sync`,
- **WHEN** their top-level config is read,
- **THEN** each SHALL declare a non-empty `concurrency.group` that no other bot uses, with
  `cancel-in-progress: false`.

- **Test:** `tests/test_bot_pipeline_isolation.py::test_every_bot_has_its_own_concurrency_group`
