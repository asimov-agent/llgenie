## ADDED Requirements

### Requirement: the arms gate reads the board the merge lane reads (queue semantics)

The arms gate (`scripts/check_arms.py`, `make check-arms`) SHALL classify an open PR as **finished** only when
its `statusCheckRollup` is terminal and GREEN — every row COMPLETED and no row concluded
FAILURE/CANCELLED/TIMED_OUT/START_FAILURE. A rollup with a QUEUED/IN_PROGRESS row, an empty rollup, a RED
rollup, a draft base-mismatch, or a non-mergeable state SHALL be reported as legitimately unfinished and SHALL
NOT be a finding. A finished PR SHALL satisfy rule 16 when it is **armed** (`autoMergeRequest != null`) OR
**queued** (`mergeStateStatus == CLEAN` — the CI `auto-merge` job lands it) OR its review chain is in flight
(`reviewDecision` REVIEW_REQUIRED/CHANGES_REQUESTED). A PR that is finished, review-chain-complete, and
neither armed nor queued (BLOCKED-after-approval or BEHIND) SHALL remain a named finding. The audit SHALL stay
one unfiltered `gh pr list --json` call carrying `mergeStateStatus`, `reviewDecision` and
`statusCheckRollup`, and `report` SHALL print one explicit state per open PR. (fleet rule 16 #873; queue
semantics issue #2378)

#### Scenario: mid-CI lanes are not findings

- **WHEN** every open PR has a check rollup with an IN_PROGRESS/QUEUED row or no rows yet
- **THEN** `check` exits 0 and `report` names each such PR as "in CI (checks not terminal — not finished
  yet, #2378)"

#### Scenario: the CLEAN queue row satisfies rule 16

- **WHEN** a green, approved, mergeable, main-based PR carries no `autoMergeRequest` but
  `mergeStateStatus == CLEAN`
- **THEN** it is reported as queued ("CI auto-merge job lands it") and `check` exits 0

#### Scenario: a stuck finished PR is still named

- **WHEN** a PR's checks are all COMPLETED and green, it is mergeable on the default branch, its review chain
  has landed (not REVIEW_REQUIRED/CHANGES_REQUESTED), and it carries neither `autoMergeRequest` nor a CLEAN
  queue row (BLOCKED or BEHIND)
- **THEN** `check` exits 1 and names that PR with its `mergeStateStatus`

#### Scenario: a red PR is not double-named

- **WHEN** a mergeable main-based PR's rollup finished with a FAILURE row
- **THEN** it is reported as "red (CI already names this failure)" and is not a finding
