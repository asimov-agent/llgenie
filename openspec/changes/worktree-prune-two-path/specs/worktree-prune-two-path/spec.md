# worktree-prune-two-path

## ADDED Requirements

### Requirement: a branch is prunable by PR-merged head and by ancestry, conjunctive with the open-PR and open-issue guards

A local branch/worktree MUST be considered prunable when EITHER its head is the `headRefName` of a
MERGED PR whose `mergeCommit.oid` is an ancestor of the base, OR its own head is an ancestor of the
base (ancestry-merged). A branch that names an OPEN PR, or whose `issue-NNN`/`<NNNN>-` token names
an OPEN issue, MUST be kept. A head that is AHEAD of `origin/main` MUST be kept whatever its PR/issue
state. The base's own local branch MUST never be a candidate. `--dry` MUST print the plan and mutate
nothing.

WHEN the prune plans a branch set
THEN it prunes exactly the branches that are merged (by PR commit or by ancestry) AND name no OPEN
PR AND name no OPEN issue AND are not ahead of the base, and keeps every other branch with its
stated reason.

#### Scenario: an ancestry-merged branch naming no PR and no issue is pruned

- **Given** a branch whose head is an ancestor of `origin/main`, names no PR and no open issue
- **When** the prune runs non-dry
- **Then** the branch's worktree is removed and the branch is deleted

- **Test:** `tests/test_worktree_prune.py::test_an_ancestor_branch_with_no_pr_and_no_issue_is_pruned`

#### Scenario: a head ahead of the base is never pruned

- **Given** a branch whose head is not an ancestor of `origin/main` (novel, unmerged)
- **When** the prune runs, in any mode
- **Then** the branch is kept and reported as not-an-ancestor, never deleted

- **Test:** `tests/test_worktree_prune.py::test_a_branch_ahead_of_main_is_never_pruned`

### Requirement: the open-issue gate holds a merged branch

A branch whose `issue-NNN` (or `<NNNN>-`) token names an issue in GitHub `OPEN` state MUST be kept,
however dead its head looks by ancestry or by a merged PR. A CLOSED or absent issue MUST be treated
as "not open" (it does not protect the branch).

WHEN a merged-by-ancestry branch names an issue token
THEN the branch is kept exactly when `gh issue view <token>` reports OPEN; a CLOSED or
`Could not resolve` outcome does not keep it.

#### Scenario: an open issue keeps a merged branch

- **Given** a branch `fix/1234-publish-gap` whose head is an ancestor of `origin/main`, and issue
  `1234` is OPEN
- **When** the prune runs
- **Then** the branch is kept with reason "names open issue #1234"

- **Test:** `tests/test_worktree_prune.py::test_an_ancestor_branch_naming_an_open_issue_is_kept`

#### Scenario: a closed issue does not protect a merged branch

- **Given** the same branch and issue `1234` CLOSED
- **When** the prune runs
- **Then** the branch is pruned

- **Test:** `tests/test_worktree_prune.py::test_an_ancestor_branch_naming_a_closed_issue_is_pruned`

#### Scenario: an absent issue reads as not-open

- **Given** the same branch and a `gh` that cannot resolve the token (`Could not resolve…`)
- **When** the prune runs
- **Then** the branch is pruned (absent is not a reason to keep merged work)

- **Test:** `tests/test_worktree_prune.py::test_an_ancestor_branch_naming_an_absent_issue_is_pruned`

### Requirement: the open-PR gate holds a branch, and the remote branch, whatever the head says

A branch that names an OPEN PR MUST be kept, even when its head is an ancestor of the base. The
matching `origin/<branch>` remote branch MUST also be kept while any OPEN PR names the head branch.

WHEN a branch names an OPEN PR
THEN the prune keeps the local branch and does not delete `origin/<branch>`.

#### Scenario: an open PR keeps a branch whose head is an ancestor

- **Given** a branch `feat/live-pr` whose head is an ancestor of `origin/main`, with an OPEN PR
- **When** the prune runs
- **Then** the branch and worktree are kept, reported "PR #N is OPEN"

- **Test:** `tests/test_worktree_prune.py::test_an_open_pr_keeps_a_branch_even_when_its_head_is_an_ancestor`

#### Scenario: a live open PR keeps the remote branch

- **Given** a branch with a pushed `origin/<branch>` and an OPEN PR naming it
- **When** the prune runs
- **Then** the remote branch is kept (no deletion line in the output)

- **Test:** `tests/test_worktree_prune.py::test_a_live_open_pr_keeps_the_remote_branch`

### Requirement: the merged remote branch is deleted when no open PR, and the make target and tick were aligned

After pruning a local branch, the matching `origin/<branch>` remote branch MUST be deleted when it
is merged and no open PR names it. The `##` help line for `make worktree-prune` MUST state the
two-path eligibility and the anti-merge safety, and the orchestrator tick's STEP 10 MUST call the
canonical `make reclaim-tmp-worktrees DRY=0` /tmp pass (never FORCE).

WHEN a merged branch with an `origin/` remote and no open PR is pruned
THEN the remote branch is deleted too, and the emitted plan/report names it.

#### Scenario: the merged remote branch is deleted when no open PR

- **Given** a PR-merged branch whose `origin/` remote still exists and names no live PR
- **When** the prune runs non-dry
- **Then** `origin/<branch>` is deleted and the report lines "removed origin/<branch>"

- **Test:** `tests/test_worktree_prune.py::test_the_merged_remote_branch_is_deleted_when_no_open_pr`

#### Scenario: the help line names the two-path rule

- **Given** `make help` on the branch
- **Then** the `worktree-prune` help line states "proven by the PR's merge commit OR by ancestry" and
  the anti-merge bound on heads ahead of the base

- **Test:** the Makefile `worktree-prune:` `##` help line itself

#### Scenario: the tick /tmp pass is the canonical reclaim target

- **Given** the orchestrator tick prompt's STEP 10
- **Then** its /tmp step names `make reclaim-tmp-worktrees DRY=0`, the ancestry-gated pass, and
  states that FORCE stays the #794-guarded owner exception never used as a pass step

- **Test:** `agents/llgenie-planner/prompts/llgenie-orchestrator-tick.md` STEP 10 text
