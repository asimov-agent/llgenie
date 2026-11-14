# Delta spec: agent-profile-drift-gate (reconcile-lane-skill-drift)

## ADDED Requirements

### Requirement: Drift reconciliation honours landed OpenSpec decisions

When `make check-agent-profiles` reports a per-lane drift finding, the
reconciliation MUST first establish which side carries knowledge that the other
has never held. A live-side sentence whose exact text exists in the tree's
history and was deliberately retired by a merged OpenSpec change MUST NOT be
re-folded into the tree; the tree copy (the landed decision) is authoritative
and the finding is cleared by the tree→live sync the gate prescribes
(`make sync-agent-profile PROFILE=<lane>`). Only live text with no tree-history
ancestry is folded into the tree via the lane's PR.

#### Scenario: retired force-push text is not resurrected

- **WHEN** a drift finding's live-only line is within the touched-file set of
  merged change #2502 (#2510, commit 6e3f25ffc) rewriting `--force-if-includes`
  discipline
- **THEN** the tree copy stays byte-identical to the post-#2510 text
- **AND** the finding is cleared by re-syncing the lane profile from the tree

#### Scenario: new live knowledge is folded into the tree

- **WHEN** a live file was edited after its profile install and carries text
  that never existed in any tree revision (`git log -S` finds no ancestor)
- **THEN** the lane PR folds that text into `agents/<lane>/...` unchanged
- **AND** `make check-agent-profiles` exits 0 with no per-lane FAIL once the
  lane profiles are re-synced from the reconciled tree
