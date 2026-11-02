# worktree-base-origin-main

## ADDED Requirements

### Requirement: a worktree's base is `origin/main`, never the primary checkout's HEAD

Every created worktree MUST be cut from `refs/remotes/origin/main` (after
fetching `origin main` when needed), never from the primary checkout's
currently checked-out branch. The base the worktree was cut from MUST be
recorded/provable.

WHEN a worktree is created while the primary checkout is parked on a PR branch,
THEN the new worktree's `HEAD == refs/remotes/origin/main`, NOT the parked
branch's tip.

#### Scenario: a worktree cut while the primary checkout is on a PR branch lands on origin/main

- **Given** the primary checkout is deliberately checked out to a PR branch
  (differing commits from `origin/main`)
- **When** the worktree-creation path creates a new worktree
- **Then** `git rev-parse HEAD` of the new worktree equals
  `git rev-parse refs/remotes/origin/main`
- **And** the base sha equals `refs/remotes/origin/main`, never the parked HEAD
- **Test:** `tests/test_worktree_base.py::test_a_worktree_cut_while_the_primary_is_parked_lands_on_origin_main`

#### Scenario: the base ref is fetched before use

- **Given** `refs/remotes/origin/main` may be stale or absent
- **When** the worktree-creation path runs
- **Then** it fetches `origin main` and resolves the base from the fetched ref
- **Test:** `tests/test_worktree_base.py::test_the_base_is_fetched_before_use`

### Requirement: the PR body records the base sha beside the `AGENTS:` line

A bot PR body MUST carry a `BASE: <sha> (== origin/main at open)` line directly
beside the existing `AGENTS: <sha> <bytes>b <lines>l` line, so a reviewer can
check the base without the branch.

WHEN the bot preflight produces the record,
THEN it includes the `AGENTS:` line AND a `BASE:` line naming the measured
`origin/main` commit at open.

#### Scenario: the preflight record carries both lines

- **Given** a clean checkout at `origin/main`
- **When** `bot_preflight.py` renders the record
- **Then** the record contains `AGENTS: <sha> <bytes>b <lines>l`
- **And** the record contains `BASE: <sha> (== origin/main at open)`
- **Test:** `tests/test_bot_preflight_base_line.py::test_the_record_carries_the_base_line_beside_the_agents_line`

### Requirement: a gate fails a PR whose merge-base is not `origin/main` itself

A gate MUST fail a PR when `git merge-base refs/remotes/origin/main HEAD` is not
`refs/remotes/origin/main` itself (the branch carries commits from another PR),
naming the foreign commit. The gate MUST stay green for a clean branch one
commit ahead of `origin/main` (the negative control).

WHEN a branch's merge-base with `origin/main` is not `origin/main`,
THEN the gate exits non-zero and names the foreign commit.
WHEN a branch is exactly one commit ahead of `origin/main` with a clean
merge-base,
THEN the gate exits zero.

#### Scenario: a branch carrying another PR's commits fails, naming the foreign commit

- **Given** a branch whose merge-base with `origin/main` is an older commit
  (foreign commits present)
- **When** the gate runs
- **Then** it exits non-zero
- **And** its message names the foreign commit
- **Test:** `tests/test_check_pr_base.py::test_a_foreign_commit_fails_and_is_named`

#### Scenario: a clean branch one commit ahead of origin/main passes

- **Given** a branch cut from `origin/main` with exactly one commit ahead
- **When** the gate runs
- **Then** it exits zero
- **Test:** `tests/test_check_pr_base.py::test_a_clean_one_ahead_branch_passes`

### Requirement: the primary checkout is measured and reported

The reporting target MUST measure and report the primary checkout's currently
checked-out branch, its ahead/behind count versus the base, and any uncommitted
paths. It MUST never auto check out a branch and never prune.

WHEN the reporting target runs,
THEN it lists the primary checkout's branch, its ahead/behind counts versus the
base, and any uncommitted paths,
AND it does not mutate the checkout or remove any worktree.

#### Scenario: the primary checkout's branch, drift and dirt are reported

- **Given** a primary checkout whose branch, ahead/behind count and uncommitted
  paths are known
- **When** the reporting target runs
- **Then** the output carries the primary checkout's branch
- **And** its ahead/behind count versus the base
- **And** its uncommitted paths
- **Test:** `tests/test_worktree_report_drift.py::test_the_report_reads_the_primary_checkouts_branch_drift_and_dirt`
