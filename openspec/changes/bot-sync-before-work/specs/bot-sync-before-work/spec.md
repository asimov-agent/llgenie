# bot-sync-before-work

## ADDED Requirements

### Requirement: a bot syncs with upstream main before it starts work

Every bot that begins work SHALL first sync with the latest upstream `main`: the implementer SHALL
base a new branch on it, and the fix-bot SHALL rebase an existing PR's branch onto it. A bot that
cannot reach `main` SHALL NOT start.

#### Scenario: the implementer starts from latest main

- **GIVEN** a checkout whose `main` has advanced since the run began,
- **WHEN** the implementer runs `make bot-sync-main`,
- **THEN** the working tree is exactly upstream `main`'s tree and the branch it pushes is based on it.

- **Test:** `tests/test_bot_sync.py::test_reset_makes_the_tree_exactly_latest_main`

#### Scenario: the fix-bot repairs on a current base

- **GIVEN** a PR branch forked from an older `main`, and upstream `main` since advanced,
- **WHEN** the fix-bot runs `make bot-sync-branch`,
- **THEN** the branch contains latest `main` and still carries its own commits, and the repair loop
  runs on that tree.

- **Test:** `tests/test_bot_sync.py::test_rebase_puts_the_branch_on_latest_main`

### Requirement: a conflicting sync is reported, never forced

A sync that does not apply cleanly SHALL abort, leave the branch exactly as it found it, and exit 2
so the caller can stand down. Conflict resolution is the rebase-bot's responsibility (#246).

#### Scenario: a conflicting branch is left untouched

- **GIVEN** a branch whose commit edits the same line upstream `main` moved,
- **WHEN** the fix-bot runs `make bot-sync-branch`,
- **THEN** the exit code is 2, the branch's commit and tree are unchanged, no rebase is left in
  progress, and the message names the rebase-bot.

- **Test:** `tests/test_bot_sync.py::test_a_conflict_is_reported_and_left_to_the_rebase_bot`

#### Scenario: the fix-bot reports the conflict instead of repairing

- **GIVEN** a sync that exits 2,
- **WHEN** the fix-bot's workflow evaluates the sync step,
- **THEN** it emits a notice that the PR is left to the rebase-bot and does not repair on a stale base.

- **Test:** `tests/test_bot_sync.py::test_the_bots_wire_the_sync_into_their_workflows`

### Requirement: an unreachable upstream main is a loud failure

If upstream `main` cannot be fetched, the sync SHALL fail with a non-zero exit code and say so,
because a bot must never work from a stale base.

#### Scenario: the remote does not answer

- **GIVEN** an unreachable remote,
- **WHEN** a bot runs the sync,
- **THEN** it exits non-zero with "refusing to start".

- **Test:** `tests/test_bot_sync.py::test_an_unreachable_remote_fails_loudly`

### Requirement: the push after a sync is guarded by a lease

Because a sync rewrites history, the fix-bot's push SHALL use `--force-with-lease` against the PR's
own head remote, so a concurrent push by another bot is rejected loudly rather than clobbered.

#### Scenario: another bot pushed meanwhile

- **GIVEN** a sync rewrote the branch and another bot pushed in the meantime,
- **WHEN** the fix-bot pushes,
- **THEN** the push is rejected (the lease does not match) and nothing is clobbered.

- **Test:** `tests/test_bot_sync.py::test_the_bots_wire_the_sync_into_their_workflows`
