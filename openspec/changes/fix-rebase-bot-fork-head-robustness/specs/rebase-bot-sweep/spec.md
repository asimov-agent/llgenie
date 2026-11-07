# rebase-bot-sweep

## MODIFIED Requirements

### Requirement: a fork-head fetch fault is a named skip, never a wrong-branch rebase

`scripts/rebase_bot.sh` MUST bring the PR's head branch into the runner's object store with a
bounded retry (3 attempts) AND verify `refs/remotes/<remote>/<branch>` actually exists before
`git checkout -B`. A fetch that cannot make the ref land — a transient object-write fault in the
runner's `.git/objects` (the #1926 class) or an unreachable remote — MUST stop THIS PR with a
`gave-up` comment naming the failure and a non-zero exit, leaving the sweep free to continue other
PRs. The actor MUST NOT proceed to `git rebase` a branch that was never checked out; after the
checkout it verifies HEAD is on `$HEAD_BRANCH` and refuses otherwise (a wrong-vehicle rebase/push).

WHEN the actor fetches the PR's head and the object store faults or the ref does not land
THEN the actor stops this PR with a named error, the tree is untouched, and the sweep continues.

#### Scenario: a fork fetch that faults is a named skip, not a rebase of the wrong branch
- **Given** a PR whose head repository cannot be fetched (a transient `.git/objects` write fault
  or an unreachable remote)
- **When** `scripts/rebase_bot.sh` runs
- **Then** it exits non-zero, posts a `gave-up` comment naming the fetch failure, exercises no
  `git rebase`, and leaves the currently-checked-out branch untouched
- **Test:** `tests/test_rebase_bot_sweep.py::test_a_fork_fetch_object_fault_is_a_named_skip_not_a_wrong_branch_rebase`

### Requirement: a transient push-time re-read fault is retried, a persistent one still refuses

The push-time dead-vehicle re-read (issue #1733) runs `gh pr view --json state,merged` right
before the force-push. A SINGLE transient fault (rc=1 or an empty relayed answer) MUST be retried
up to 3 times so one glitch does not redden the whole sweep (the #1602/#1603 discipline). A read
that still fails after the retries, or that answers a confirmed closed/merged state, MUST stop the
run with a `gave-up` comment and no push — the fail-closed refusal is NOT weakened.

WHEN the push-time `gh pr view` faults transiently
THEN the actor retries it; a later successful read lets the push proceed and the branch is
force-pushed to the PR's head remote.

#### Scenario: a transient push-time read fault is retried and the branch is pushed
- **Given** a rebase that reached the push-time re-read and a `gh pr view` that faults once
  (rc=1) then answers open/unmerged
- **When** `scripts/rebase_bot.sh` runs
- **Then** the retry succeeds, the branch is force-pushed to the head remote, and the run exits 0
- **Test:** `tests/test_rebase_bot_sweep.py::test_a_transient_push_time_read_fault_is_retried_not_fatal`

#### Scenario: a persistently unreadable PR is still refused
- **Given** a rebase whose push-time `gh pr view` keeps faulting through all 3 attempts
- **When** `scripts/rebase_bot.sh` runs
- **Then** it exits non-zero with a `gave-up` refusal, no push fires, and the branch is untouched
- **Test:** `tests/test_rebase_bot_sweep.py::test_a_persistent_push_time_read_fault_still_refuses`
