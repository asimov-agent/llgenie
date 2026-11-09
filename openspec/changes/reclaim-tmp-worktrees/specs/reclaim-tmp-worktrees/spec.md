# reclaim-tmp-worktrees

## ADDED Requirements

### Requirement: a registered worktree is reclaimed only when clean AND on-main AND idle

The collector MUST remove a **registered** worktree (present in `git worktree list` under the scan
root) only when all three hold: (a) the tree is clean (no uncommitted/untracked files a `git status
--porcelain` would name), (b) its `HEAD` is an ancestor of `origin/main`, (c) it is idle (mtime of
`HEAD`/`MERGE_HEAD` or the worktree's earliest mtime) >= `MIN_IDLE_MIN` (default 1). Any tree failing
a condition MUST be kept and reported with its exact reason. `DRY=1` (default) MUST delete and pin
NOTHING.

WHEN the collector scans the registered worktrees under the root
THEN it removes exactly those that are clean AND on-main AND idle, and keeps every other one with its
stated reason.

#### Scenario: a clean, on-main, idle worktree is reclaimed

- **Given** a registered worktree whose `HEAD` is an ancestor of `origin/main`, clean, and idle
  beyond `MIN_IDLE_MIN`
- **When** the collector runs with a non-dry setting
- **Then** the worktree is removed and reported

#### Scenario: a dirty worktree is kept, even with FORCE=1

- **Given** a registered worktree with uncommitted files
- **When** the collector runs, in any mode including `FORCE=1`
- **Then** the worktree is kept and the uncommitted-files refusal is reported; forced removal never
  drops the dirty refusal

#### Scenario: a head not on origin/main and an active tree are kept unless FORCE

- **Given** a clean tree whose `HEAD` is not an ancestor of `origin/main`, and a clean tree idle
  below `MIN_IDLE_MIN`
- **When** the collector runs without `FORCE=1`
- **Then** both are kept; with `FORCE=1` the on-main and idle tests are dropped (the dirty one is
  still never removed)

### Requirement: every novel head is pinned before forced removal

Before any `FORCE=1` removal of a tree whose `HEAD` exists on no remote ref, the collector MUST pin
that head as `refs/reclaimed/<worktree-name>` inside the collector's repo, then verify it with
`git for-each-ref refs/reclaimed`, and MUST NOT remove the tree if the pin is not verified. The
reported removal line MUST carry the pinned sha.

WHEN a forced removal targets a novel head
THEN the head is pinned (and verified) as `refs/reclaimed/<worktree-name>` before any removal, and
the report names the pinned sha.

#### Scenario: a forced removal of a novel head pins it first

- **Given** a clean, idle worktree whose `HEAD` exists on no remote ref
- **When** the collector runs with `FORCE=1` and non-dry
- **Then** `git for-each-ref refs/reclaimed` confirms `refs/reclaimed/<worktree-name>` names the head
  sha and the removal line reports the pinned sha before the tree is removed

#### Scenario: a dry run writes no pin

- **Given** the same novel-head worktree
- **When** the collector runs with `FORCE=1 DRY=1`
- **Then** nothing is removed and `git for-each-ref refs/reclaimed` shows no new pin

### Requirement: deregistered debris is cleared only when cache-only and head-pinned

A second pass MUST consider a directory under the scan root **absent** from `git worktree list`
(deregistered debris). It MAY delete such a directory only when it is cache-only (>=1 root-owned
`__pycache__`/`.pytest_cache`, zero asimov-owned files) or a `.git` remnant, AND its head is pinned
(as `refs/reclaimed/*`). Debris with an unpinned novel head MUST be reported and never deleted. The
four operator directories (`/tmp/Notification Cache`, `/tmp/hf`, `/tmp/gatepkg`, `/tmp/1898-unzip`
shapes) MUST be excluded as fixtures, never touched. Root-owned leftovers a lane cannot delete MUST
be reported with the exact `sudo rm -rf <path>` remedy instead of being retried.

WHEN the collector scans deregistered debris under the root
THEN it clears only cache-only (or `.git`-remnant) head-pinned directories, excludes the four
operator-dir shapes, reports unpinned-novel debris as never-deleted, and reports root-blocked
leftovers with the exact `sudo rm -rf <path>` remedy.

#### Scenario: a head-pinned cache-only debris directory is cleared

- **Given** a directory under the root absent from `git worktree list`, holding a root-owned
  `__pycache__`, zero asimov-owned files, and whose head is pinned as `refs/reclaimed/*`
- **When** the collector runs non-dry
- **Then** the directory is cleared and reported

#### Scenario: an operator directory is never considered

- **Given** a directory matching the `/tmp/Notification Cache`, `/tmp/hf`, `/tmp/gatepkg` or
  `/tmp/1898-unzip` shape
- **When** the collector scans
- **Then** it is excluded as a fixture and never touched

#### Scenario: an unpinned-novel debris head is reported, never deleted

- **Given** a debris directory whose head is not pinned (no `refs/reclaimed/*`)
- **When** the collector scans
- **Then** it is kept and reported as never-deleted (an unpinned novel head must not be destroyed)

#### Scenario: a root-blocked leftover carries the sudo remedy

- **Given** a root-owned leftover the collector cannot delete
- **When** the collector scans
- **Then** it is report with the exact `sudo rm -rf <path>` remedy and not retried

### Requirement: make target is DRY=1 by default and wired into the host-space step

`make reclaim-tmp-worktrees` MUST default to `DRY=1` (`DRY=0` to act), pass `FORCE=1` through, honour
`SCAN_ROOT=`/`REPO=`/`MIN_IDLE_MIN=` overrides, be declared in `.PHONY:`, and carry a `##` help line
beside its neighbouring targets. The docs host-space step MUST name the target by name.

WHEN an operator runs `make reclaim-tmp-worktrees`
THEN it defaults to dry-run (nothing deleted/pinned) and honours the documented overrides.

#### Scenario: the default invocation is a dry run

- **Given** an operator runs `make reclaim-tmp-worktrees` with no variables
- **Then** it behaves as `DRY=1`: nothing is deleted or pinned, and the summary prints the dry-run
  status

#### Scenario: DRY=0 and FORCE=1 pass through

- **Given** an operator runs `make reclaim-tmp-worktrees DRY=0 FORCE=1`
- **Then** the collector acts (subject to the never-dropped dirty refusal) and the forced path is
  armed
