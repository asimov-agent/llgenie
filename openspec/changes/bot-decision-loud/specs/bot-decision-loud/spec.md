# bot-decision-loud

## ADDED Requirements

### Requirement: a crashed bot decision fails the step

Every workflow step that runs a bot decision target (`…-sweep`, `…-pick`, `…-dispatch`) SHALL exit
non-zero when that target exits non-zero. A crash of the decision command SHALL NOT be read as
"nothing to do", because the run then concludes green while the bot never worked.

#### Scenario: a crashed decision fails the step

- **GIVEN** every step in `.github/workflows/*.yml` that runs a decision target,
- **WHEN** that step's shell is run with a `make` on `PATH` that exits non-zero,
- **THEN** the step exits non-zero.

- **Test:** `tests/test_bot_decision_loudness.py::test_a_crashed_decision_fails_the_step`

#### Scenario: the issue-bot's dispatch step reports which target crashed

- **GIVEN** `issue-bot.yml`'s dispatch step (which captured `rc` and never consulted it),
- **WHEN** `make issue-bot-dispatch` exits 7,
- **THEN** the step fails and its message names `issue-bot-dispatch` and `rc=7`.

- **Test:** `tests/test_bot_decision_loudness.py::test_the_step_that_had_no_check_now_reports_the_crash`

#### Scenario: a decision that answers cleanly leaves the step green

- **GIVEN** `issue-bot.yml`'s dispatch step,
- **WHEN** the decision command exits 0 and prints its machine-readable answer,
- **THEN** the step concludes success (the rule is not "always fail").

- **Test:** `tests/test_bot_decision_loudness.py::test_a_decision_that_succeeds_leaves_the_step_green`

### Requirement: the rule's scope is derived from the tree

The set of steps the rule covers SHALL be read from the workflow files, so a bot workflow added later
is covered the moment it exists, and the workflows whose swallowed decision was measured SHALL be in
that set.

#### Scenario: the measured workflows are covered

- **GIVEN** the workflows on disk,
- **WHEN** the decision steps are collected,
- **THEN** `issue-bot.yml`, `issue-refiner.yml` and `rebase-bot.yml` are all in the set.

- **Test:** `tests/test_bot_decision_loudness.py::test_the_decision_steps_are_what_this_file_covers`

### Requirement: the guard cannot pass for the wrong reason

Because the step's shell is executed by the test, a `${{ … }}` left in a `run:` block would crash
bash and make a step look loud when it is not. The harness SHALL substitute a GitHub expression the
way the runner does, and that substitution SHALL itself be asserted.

#### Scenario: an expression is substituted before the step runs

- **GIVEN** a step whose `run:` block contains `${{ github.repository }}`,
- **WHEN** the harness runs it,
- **THEN** bash sees a substituted value, the step succeeds, and no `${{` reaches the output.

- **Test:** `tests/test_bot_decision_loudness.py::test_a_github_expression_in_a_step_is_substituted_before_it_runs`
