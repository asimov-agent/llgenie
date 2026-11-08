## ADDED Requirements

### Requirement: the rebase sweep measures staleness from lineage, never from the merge state

The rebase sweep SHALL decide that a PR is behind by measuring the PR head's merge-base against
the base ref, using the same definition `check-pr-base` enforces, and SHALL NOT rely on
`mergeStateStatus` to prove a branch is fresh or stale.

`mergeStateStatus` reports `BLOCKED` whenever a required review is pending or a check is failing,
and `UNSTABLE` for a failing check. A branch that is behind `main` therefore does not carry
`BEHIND`, so a state-only read classifies it `NONE` and the sweep passes over the one rebase it
exists to perform (issue #2071; measured 2026-11-08 on six open PRs that were simultaneously
`BLOCKED`, `MERGEABLE` and behind, with a live dispatch reporting `rebased: 0`).

#### Scenario: a blocked, mergeable, genuinely-behind PR is rebased

- **GIVEN** an open PR against `main` whose `mergeStateStatus` is `BLOCKED` and whose `mergeable`
  is `MERGEABLE`
- **AND** whose head's merge-base with `main` is an older commit than `main`'s tip
- **WHEN** the sweep classifies it
- **THEN** the outcome is `REBASE`, not `NONE`
- **AND** the decision records that it was measured behind, and the reason line names it
- **Test:** `tests/test_rebase_bot_sweep.py::test_a_blocked_mergeable_pr_that_is_behind_is_rebased_not_none`

#### Scenario: a blocked PR that is not behind is passed over with a stated reason

- **GIVEN** an open PR whose `mergeStateStatus` is `BLOCKED` and whose merge-base with `main` IS
  `main`'s tip
- **WHEN** the sweep classifies it
- **THEN** the outcome is not `REBASE`, and the pass-over reason states it was measured NOT behind
- **Test:** `tests/test_rebase_bot_sweep.py::test_a_fresh_pr_is_reported_as_measured_not_behind`

#### Scenario: an unreadable staleness read is never treated as "not behind"

- **GIVEN** an open PR whose staleness measurement cannot be read
- **WHEN** the sweep classifies it
- **THEN** the outcome is not `REBASE` and the reason states the staleness could not be measured
  (a failed read is never a decision, issue #801)
- **Test:** `tests/test_rebase_bot_sweep.py::test_an_unreadable_compare_is_never_read_as_not_behind`

### Requirement: a measured-behind PR is the rebase bot's even when it is red

The sweep SHALL take a measured-behind PR for rebase even when its checks are red, and SHALL defer
a red PR to the fix-bot only when the PR is not measured behind. The rebase is the precondition for
the staleness gate `check-pr-base`, which no code repair can satisfy (issue #2071, half B).

#### Scenario: a behind PR whose only red is the staleness gate is not deferred to the fix-bot

- **GIVEN** an open PR that is measured behind `main` and whose checks are failing because of the
  staleness gate
- **WHEN** the sweep applies its bot-coexistence rules
- **THEN** the PR is taken for rebase rather than deferred to the fix-bot
- **Test:** `tests/test_rebase_bot_sweep.py::test_a_behind_pr_whose_only_red_is_the_staleness_gate_is_taken_not_deferred`

#### Scenario: a red PR that is not behind still belongs to the fix-bot

- **GIVEN** an open PR with a failing check that is measured NOT behind `main`
- **WHEN** the sweep applies its bot-coexistence rules
- **THEN** the PR is passed over with the fix-bot stated as the owner
- **Test:** `tests/test_rebase_bot_sweep.py::test_a_red_pr_that_is_behind_but_not_measured_behind_still_belongs_to_the_fix_bot`

### Requirement: the checks-in-flight skip is preserved regardless of staleness

The sweep SHALL still skip a PR with checks in flight, even when that PR is measured behind, because
a rebase force-pushes and would cancel the run that is deciding the PR.

#### Scenario: a behind PR with a running check is skipped

- **GIVEN** an open PR measured behind `main` with a check in flight
- **WHEN** the sweep classifies it
- **THEN** the PR is skipped and the reason names the in-flight run
- **Test:** `tests/test_rebase_bot_sweep.py::test_checks_in_flight_still_skip_a_pr_that_is_behind`
