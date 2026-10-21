# auto-merge-fork-head

## ADDED Requirements

### Requirement: The owner's fork is an accepted PR head

The `auto-merge` job SHALL accept a pull request whose head repository is the base repository **or** the
owner's fork (`andyholst/llgenie`) — the branch this repository's agents actually push to — and SHALL keep
it manual for any other fork.

WHEN the job's head condition is read
THEN it SHALL allow the base repo and exactly one fork owner, and every other guard (non-draft, not `main`,
every needed job `success`, not `failure()`/`cancelled()`) SHALL still apply.

#### Scenario: a head from the owner's fork is accepted

Given a green, conflict-free PR whose head is `andyholst/llgenie`
When  the `auto-merge` job evaluates its condition
Then  the fork owner is allowed, so the job runs instead of being skipped.

- **Test:** `tests/test_auto_merge.py::test_the_workflow_accepts_the_owners_fork_and_no_other`

#### Scenario: any other fork stays manual

Given a PR whose head is some third-party fork
When  the condition is read
Then  it is not matched, so the job never merges a stranger's branch.

- **Test:** `tests/test_auto_merge.py::test_the_workflow_accepts_the_owners_fork_and_no_other`

### Requirement: A fork merge never deletes a branch it cannot reach

When the head repository is not the base repository, the merge SHALL omit `--delete-branch`: the base token
cannot delete a branch in the fork, and asking it to would fail a run whose merge already succeeded.

WHEN a PR from the fork is merged by the job
THEN the merge argv SHALL NOT carry `--delete-branch`, and the log SHALL say the branch was kept; a
same-repository head SHALL still delete its branch.

#### Scenario: a fork head merges without --delete-branch

Given a green, clean PR whose head repository is the fork
When  `make auto-merge` merges it
Then  `gh pr merge` runs with `--squash --match-head-commit` and without `--delete-branch`.

- **Test:** `tests/test_auto_merge.py::test_a_fork_head_merges_without_deleting_the_branch`

#### Scenario: a same-repo head still deletes its branch

Given a green, clean PR whose head repository is the base repository
When  `make auto-merge` merges it
Then  `--delete-branch` is present.

- **Test:** `tests/test_auto_merge.py::test_the_merge_is_squash_head_pinned_and_branch_deleted`
