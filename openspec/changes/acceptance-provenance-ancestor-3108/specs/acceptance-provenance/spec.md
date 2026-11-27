# Spec: acceptance provenance resolution

## ADDED Requirements

### Requirement: an ancestor head proves a ticked acceptance criterion

`check_pr_acceptance` SHALL treat a ticked criterion's `(proven: …)` head reference as
current when it equals the measured `--rev` sha OR when `git merge-base --is-ancestor
<proven-head>^{commit} <measured-rev>^{commit}` succeeds. An ancestor proof is a proof
measured earlier in the same history; a rebase/push that keeps that commit in the
PR's ancestry SHALL NOT produce `tick-stale-head-unflagged`.

#### Scenario: proof measured at an ancestor survives a push

- **Given** a ticked criterion proven at sha `P`, the current head `H` descends from `P`,
  and the cited run concluded `success` (or the marker is a command+`rc`+`sha` tick),
- **when** the gate measures the criterion against `H`,
- **then** no `tick-stale-head-unflagged` finding is emitted for that criterion.

#### Scenario: unrelated head still reds

- **Given** a ticked criterion proven at sha `S` that is NOT an ancestor of the measured head
  `H` (a sibling commit off base, or a commit from another branch),
- **when** the gate measures the criterion against `H`,
- **then** the blocking `tick-stale-head-unflagged` finding is emitted, unchanged from the
  current behaviour.

#### Scenario: unresolvable or non-commit reference still reds

- **Given** a `(proven: …)` head token that cannot be resolved to a commit, or a token whose
  object is not a commit,
- **when** the gate resolves provenance,
- **then** the reference is NOT treated as an ancestor and the blocking stale-head finding
  remains; an unreadable proof is never accepted.

### Requirement: the live-run evidence rules stay intact

The ancestor seam SHALL apply only after the gate has verified that any cited `run=` is
readable and concluded `success`. A tick citing a red, cancelled or unreadable run SHALL
still emit its blocking finding regardless of the head's ancestry. No check-pr-acceptance
gate step SHALL be skipped or weakened.

#### Scenario: ancestor proof citing a red run

- **Given** a ticked criterion proven at an ancestor head but citing a run whose live
  conclusion is `failure`,
- **when** the gate measures the criterion,
- **then** `tick-cites-red-run` is emitted and the criterion is not proven.

#### Scenario: regression tests cover both classes

- **Given** a temporary git repository with a base commit, a child head and an unrelated
  sibling commit,
- **when** `tests/test_check_pr_acceptance.py` exercises the ancestor seam,
- **then** the ancestor case is clean and the unrelated/missing case emits
  `tick-stale-head-unflagged`.
