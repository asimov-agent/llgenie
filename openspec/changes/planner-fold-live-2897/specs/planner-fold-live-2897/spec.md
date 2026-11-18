## ADDED Requirements

### Requirement: The planner lane reconciles live-side from the tree's split shape, loss-verified before the write

The planner lane finding SHALL be reconciled by `make sync-agent-profile PROFILE=llgenie-planner`
run deliberately with `FORCE=1`, after a recorded line-set comparison shows the tree's whole lane
store (SKILL.md plus `references/`) carries every live-only content line verbatim — the comparison
result (live-only line count, matched-line count) SHALL be recorded in the change before the sync
runs, so the sync's shrink refusal reason is answered by measurement, not assumption.

#### Scenario: shrink is proven lossless

- **WHEN** the live SKILL.md is longer than the tree copy and every live-only content line appears
  verbatim in a tree `references/` file the tree body links
- **THEN** the reconciliation is the forced tree-to-live sync, and the post-sync gate run names no
  finding for the lane

#### Scenario: nothing is versioned twice

- **WHEN** the reconciliation completes
- **THEN** no new tree copy of the live-only block exists (the existing reference carries it), the
  planner `SKILL.md` in the tree carries a bumped version stamp, and the pair of docs records
  (agent-wiki note, `docs/changes.d/` row) lands in the same commit as the stamp

### Requirement: The profile-drift gate reads zero findings fleet-wide

Once every flagged lane is reconciled, `make -s check-agent-profiles` SHALL print zero findings on a
host running the folded profiles, and that run SHALL be replayable proof (rc + head) recorded on the
issue that tracked the finding list.

#### Scenario: the 586-finding list closes at zero

- **WHEN** the planner lane lands as the last reconciliation
- **THEN** a `make -s check-agent-profiles` run at the lane head prints `0 finding(s)`, and the
  umbrella issue's fleet-wide-zero acceptance item is ticked with that replayable proof before the
  umbrella closes
