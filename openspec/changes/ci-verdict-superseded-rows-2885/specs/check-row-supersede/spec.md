## ADDED Requirements

### Requirement: Newest concluded check-run row per name and workflow governs the head
The system SHALL treat, for each (job name, workflow file) pair present in a head's check-run rows, only the newest CONCLUDED row (by `started_at`, tie-broken by row id) as that group's verdict. Every strictly-older concluded row in the group SHALL be superseded: it SHALL NOT block `ci-verdict`'s unjudged-red scan and SHALL NOT be a deferral reason for `auto-merge`. A row that has not concluded (status queued or in_progress) SHALL neither supersede another row nor be superseded. A row whose workflow file cannot be resolved SHALL never be superseded and SHALL never supersede another row. `scripts/head_check_rows.py` SHALL be the single implementation used by BOTH `scripts/ci_verdict.py` and `scripts/auto_merge.py`.

#### Scenario: A superseded scope red no longer blocks the verdict
- **WHEN** a head carries a `scope` failure row from an older `ci-scope.yml` run and a newer `scope` success row from the same workflow file at the same head
- **AND** the head's judged roster is fully green
- **THEN** `unjudged_reds` returns no blocker naming the dead row
- **AND** the verdict posts `conclusion=success`

#### Scenario: The newest red still blocks
- **WHEN** a head carries two concluded red rows of the same job name and workflow file
- **THEN** only the newest of them is reported as an unjudged red
- **AND** the verdict still posts `conclusion=failure`

#### Scenario: An unfinished run does not clear an older red
- **WHEN** a head carries a concluded red row and a queued or in_progress row of the same job name and workflow file
- **THEN** the red row is NOT superseded and still blocks

#### Scenario: auto-merge defers only on the newest concluded red
- **WHEN** `failing_checks` sees a red row whose (job name, workflow file) group has a newer concluded green row
- **THEN** the red row is not part of the deferral reason
- **AND** when the group's newest concluded row is red, the deferral reason names that newest row

#### Scenario: The pinned parity between the verdict and the merger stays
- **WHEN** `tests/test_ci_verdict.py::test_the_blocking_conclusions_are_the_merger_s_rule` runs
- **THEN** `UNJUDGED_RED_CONCLUSIONS` remains exactly `auto_merge.RED_CONCLUSIONS`
