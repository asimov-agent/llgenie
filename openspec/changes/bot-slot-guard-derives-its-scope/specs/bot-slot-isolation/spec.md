# bot-slot-isolation

## ADDED Requirements

### Requirement: the guard's scope is derived, never hand-listed

The slot guard SHALL read the workflow directory and treat **every** workflow that declares a
`schedule:` as a bot, so a newly merged bot is inside the guard without anyone editing the test.

#### Scenario: a narrowed list fails

- **GIVEN** the workflows on disk and the set the guard holds itself to,
- **WHEN** the guard's scope is compared with the workflows that declare a `schedule:`,
- **THEN** the two are equal, and the test fails if the scope is ever narrowed to a hand-written list.

- **Test:** `tests/test_bot_pipeline_isolation.py::test_the_scope_is_derived_from_the_workflow_files`

#### Scenario: the bots previously outside the guard are in scope

- **GIVEN** the bots merged after #275 (`rebase-bot`, `issue-refiner`, `code-review-bot`),
- **WHEN** the derived scope is read,
- **THEN** each one is present, and the scope is not vacuous.

- **Test:** `tests/test_bot_pipeline_isolation.py::test_the_scope_is_derived_from_the_workflow_files`

### Requirement: no two bots own the same cron slot

No two scheduled bots SHALL own the same `(minute, weekday)` slot, for **every** bot in the derived
scope.

#### Scenario: the re-staggered crons share no slot

- **GIVEN** the nine scheduled bots and their crons,
- **WHEN** each cron is expanded into the `(minute, weekday)` slots it owns,
- **THEN** no slot is owned by two bots — `rebase-bot` at `:29` and `code-review-bot` at `:31` no
  longer collide with `issue-bot` at `:23`.

- **Test:** `tests/test_bot_pipeline_isolation.py::test_no_workflow_shares_a_minute`

#### Scenario: the pre-fix crons are caught

- **GIVEN** the pre-fix crons (`rebase-bot` `23 */6 * * *`, `code-review-bot` `23 7 * * 1`),
- **WHEN** the guard runs with its scope now covering those bots,
- **THEN** it fails, naming `issue-bot`/`rebase-bot` on minute 23 for weekdays 1-6.

- **Test:** `tests/test_bot_pipeline_isolation.py::test_no_workflow_shares_a_minute` (verified red on the pre-fix crons, rule 6c)

### Requirement: an every-hour bot's minute stays reserved

A bot that does not run every hour SHALL NOT use a minute an every-hour bot holds on all seven
weekdays, with the reserved set derived from the crons.

#### Scenario: reserved minutes are derived and respected

- **GIVEN** the every-hour bots (`fix-bot` `:17`, `queued-alarm` `:07`/`:37`, `issue-refiner` `:43`),
- **WHEN** each non-every-hour bot's minutes are checked,
- **THEN** none of them uses `7`, `17`, `37` or `43`, and the reserved set is non-empty.

- **Test:** `tests/test_bot_pipeline_isolation.py::test_the_hourly_bots_minutes_are_not_reused`

### Requirement: every bot keeps its own concurrency group

Every bot in the scope SHALL declare a `concurrency:` group of its own with
`cancel-in-progress: false`.

#### Scenario: no two bots share a group

- **GIVEN** every scheduled bot,
- **WHEN** its concurrency block is read,
- **THEN** it names a group, never cancels an in-progress run, and no group is shared.

- **Test:** `tests/test_bot_pipeline_isolation.py::test_every_bot_has_its_own_concurrency_group`
