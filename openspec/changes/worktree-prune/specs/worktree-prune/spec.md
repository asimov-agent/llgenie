# worktree-prune

## ADDED Requirements

### Requirement: a branch is prunable only when GitHub proves its work landed

The prune MUST decide eligibility from the pull request, never from a branch name, a commit date or
an ancestry guess. A local branch is prunable if and only if it is the `headRefName` of a MERGED PR
and that PR's `mergeCommit.oid` is an ancestor of the base ref (`origin/main` by default). A branch
naming an OPEN PR, a CLOSED-and-unmerged PR, or no PR at all MUST be kept, and a branch whose merge
commit is not on the base MUST be kept. Every kept branch MUST print its reason, so the plan is
evidence rather than silence.

WHEN the prune reads the branch set and the merged-PR set for the base
THEN it removes exactly the branches whose PR merge commit is on the base, and keeps every other one
with its stated reason.

#### Scenario: a squash-merged branch and its clean worktree are removed

- **Given** a repository whose branch `feat/x` was squash-merged into `main`, so the branch tip is NOT an ancestor of `main`
- **And** its PR is `MERGED` with a merge commit that is on `main`
- **And** a clean worktree is checked out on `feat/x`
- **When** the prune runs against that base
- **Then** the worktree is removed, the branch is deleted, and the PR number is printed
- **Test:** `tests/test_worktree_prune.py::test_prunes_a_squash_merged_branch_and_its_clean_worktree`

#### Scenario: a dirty worktree is never force-removed

- **Given** a merged-PR branch whose worktree carries an uncommitted change
- **When** the prune runs
- **Then** both the worktree and the branch survive, and the reason names the dirty worktree
- **Test:** `tests/test_worktree_prune.py::test_a_dirty_worktree_is_kept_and_says_so`

#### Scenario: a closed or PR-less branch is kept

- **Given** a branch naming a `CLOSED` unmerged PR, and a branch naming no PR at all
- **When** the prune runs
- **Then** both survive and each reason names which case it is
- **Test:** `tests/test_worktree_prune.py::test_a_closed_or_prless_branch_is_kept`

#### Scenario: a merge commit off the base is kept

- **Given** a branch whose PR is `MERGED` but whose merge commit is not an ancestor of the base
- **When** the prune runs
- **Then** the branch survives and the reason says the merge commit is not on the base
- **Test:** `tests/test_worktree_prune.py::test_a_merge_commit_off_the_base_is_kept`

### Requirement: the main checkout, the running worktree and detached worktrees are untouchable

The prune MUST NOT remove the repository's main checkout, MUST NOT remove the worktree the run is
executing in (git refuses to remove the directory it stands in), and MUST NOT remove a worktree whose
HEAD is detached — a detached worktree holds no branch, so no merge can license deleting it.

WHEN the worktree list contains the main checkout, the current worktree or a detached worktree
THEN none of them is a candidate, whatever its commit's history says.

#### Scenario: the main checkout survives a prune

- **Given** a repository whose main checkout is also where the prune runs
- **When** the prune runs with every branch on that checkout's history merged
- **Then** the main checkout still exists and is still on its branch
- **Test:** `tests/test_worktree_prune.py::test_the_main_checkout_is_never_removed`

#### Scenario: the worktree the run is in is reported, not removed

- **Given** a merged-PR branch whose own worktree is where the prune is executed
- **When** the prune runs from inside that worktree
- **Then** it exits 0, the worktree and the branch survive, and the reason says the worktree is the
  one the run is executing in
- **Test:** `tests/test_worktree_prune.py::test_the_worktree_the_run_is_in_is_never_removed`

#### Scenario: a detached worktree is never removed

- **Given** a detached-HEAD worktree at the tip of a merged branch
- **When** the prune runs
- **Then** the detached worktree still exists, and only the branch (and any branch-holding
  worktree) is what the run decides
- **Test:** `tests/test_worktree_prune.py::test_a_detached_worktree_is_never_removed`

### Requirement: a dry run mutates nothing

`DRY=1` (equivalently `--dry`) MUST print the same plan and MUST NOT remove a worktree, delete a
branch or push anything.

WHEN the prune runs in dry mode
THEN the plan matches a live run and the repository is byte-identical afterwards.

#### Scenario: dry mode prunes nothing

- **Given** a merged-PR branch with a clean worktree, and the same repository state read twice
- **When** the prune runs with `--dry`
- **Then** the plan names the branch it would prune, and the branch and worktree both survive
- **Test:** `tests/test_worktree_prune.py::test_dry_run_prunes_nothing_and_prints_the_plan`

### Requirement: a failure is loud, never a silent partial prune

A failed GitHub lookup, a failed `git worktree remove`, or a failed `git branch -D` MUST exit
non-zero and name the failure. The prune MUST NOT continue past a failed worktree removal to delete
that branch, and MUST NOT report a clean summary after a failure.

WHEN any step of the prune fails
THEN the run exits non-zero, names the failing branch and step, and leaves that branch in place.

#### Scenario: a failed PR lookup prunes nothing and exits non-zero

- **Given** a repository with a merged-PR branch, and a `gh` that fails
- **When** the prune runs
- **Then** it exits 2, the branch and worktree survive, and the message names the `gh` failure
- **Test:** `tests/test_worktree_prune.py::test_a_failed_pr_lookup_prunes_nothing_and_exits_nonzero`

#### Scenario: a worktree that cannot be removed keeps its branch

- **Given** a merged-PR branch whose worktree git refuses to remove (a locked worktree)
- **When** the prune runs
- **Then** it exits 2, the worktree and the branch both survive, and the message names the branch and
  the failed removal
- **Test:** `tests/test_worktree_prune.py::test_a_worktree_that_cannot_be_removed_keeps_its_branch_and_exits_nonzero`

### Requirement: the target is wired, documented and phony

`make worktree-prune` MUST exist, MUST be declared in `.PHONY:` (it produces no file of its name),
MUST carry a `##` help line, MUST be named in `README.md`, and MUST pass `DRY=1` through to the
script.

WHEN the Makefile and the README are read
THEN the target, its help line, its `.PHONY` entry and its README line all exist, and `DRY=1` reaches
the script.

#### Scenario: the make target is wired, phony and documented

- **Given** the real checkout
- **When** `Makefile` and `README.md` are read
- **Then** `worktree-prune` is a target with a `##` help line, is in `.PHONY:`, is named in the
  README, and its recipe forwards `$(if $(DRY),--dry,)`
- **Test:** `tests/test_worktree_prune.py::test_the_make_target_is_phony_documented_and_forwards_dry`
