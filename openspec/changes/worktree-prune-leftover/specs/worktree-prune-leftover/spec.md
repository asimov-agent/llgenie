# worktree-prune-leftover

## ADDED Requirements

### Requirement: an undeletable worktree is a named leftover, not a failure
When `apply()` unregisters a merged branch's worktree but the directory cannot be
fully deleted (files the sweep's user does not own, a read-only directory), the run
MUST report that directory as a leftover naming its path, the reason and the one
command that clears it, MUST still delete the branch, and MUST NOT exit 2 for it.

WHEN a planned worktree removal fails and the directory survives,
THEN the run prints `[worktree-prune] leftover <path> — <reason>; clear it with: <command>`
AND exits 0.

#### Scenario: a merged worktree holding a file the user cannot delete
- **Given** a squash-merged branch whose worktree holds a directory the current user cannot write
- **When** `python3 scripts/worktree_prune.py` runs for real
- **Then** the output names the worktree path as a leftover with the command that clears it
- **And** the branch is deleted
- **And** the process exits 0
- **Test:** `tests/test_worktree_prune.py::test_a_worktree_that_cannot_be_deleted_is_reported_as_a_leftover`

### Requirement: debris is cleared through the container engine as root
Where a container engine (`nerdctl`, else `docker`) is on `PATH`, `apply()` MUST delete
the root-owned debris through it as root — the engine that created it — and then retry
the worktree removal once, so the common case leaves no leftover.

WHEN a worktree removal fails and a container engine answers,
THEN the sweep removes the directory as root inside the engine and retries the removal
AND reports no leftover when the retry succeeds.

#### Scenario: root-owned debris is cleared without a human step
- **Given** a squash-merged branch whose worktree holds an undeletable directory
- **And** a `docker` on `PATH` that deletes the mounted path as root
- **When** the prune runs for real
- **Then** the worktree and the branch are gone, the summary counts them, and no leftover is printed
- **Test:** `tests/test_worktree_prune.py::test_root_owned_debris_is_cleared_through_the_container_engine`

### Requirement: the exit code names the sweep's own state
`main()` MUST exit 0 when every planned action either happened or was reported as a
keep/leftover with its reason, and MUST exit 2 only for a step that failed without a
report (a lookup or a `git` call that could not be explained).

WHEN a run ends with leftovers and no unexplained error,
THEN the process exits 0.

#### Scenario: a half-done first run stops returning 2
- **Given** a merged worktree that cannot be removed and a branch that can be deleted
- **When** the prune runs
- **Then** the branch is gone, the leftover is printed, and the exit code is 0
- **Test:** `tests/test_worktree_prune.py::test_a_worktree_that_cannot_be_deleted_is_reported_as_a_leftover`
