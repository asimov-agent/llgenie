# auto-merge-review-approve

## ADDED Requirements

### Requirement: A deferral is explained on the PR, once per head

When `auto-merge` does not merge, it SHALL post exactly one comment per head SHA explaining why (state,
mergeability, merge state, review decision) and what would unblock it, and SHALL NOT post a second comment
for the same head. `make auto-merge-explain` SHALL print the same verdict without writing anything.

WHEN the job defers
THEN a `<!-- auto-merge: deferred <sha> -->` comment exists on the PR (only one per sha), and the run log
names the same reason.

#### Scenario: the first deferral is commented

Given a green PR whose `mergeStateStatus` is `DIRTY`
When  the job runs and defers
Then  one comment is posted naming the conflict as the reason.

- **Test:** `tests/test_auto_merge.py::test_a_deferral_is_commented_once_per_head`

#### Scenario: a second run for the same head does not comment again

Given a deferral comment already exists for the head SHA
When  the job defers again on the same head
Then  no second comment is posted.

- **Test:** `tests/test_auto_merge.py::test_a_deferral_is_commented_once_per_head`

#### Scenario: explain never writes

Given any PR
When  `make auto-merge-explain PR=<n>` runs
Then  it prints the verdict and invokes no `pr merge`, `pr review` or `issue comment`.

- **Test:** `tests/test_auto_merge.py::test_explain_prints_the_verdict_and_writes_nothing`

### Requirement: A review-blocked green PR is approved by the other allowed identity, then merged

When the only blocker is a required review (`mergeable == MERGEABLE`, `mergeStateStatus == BLOCKED`,
`reviewDecision == REVIEW_REQUIRED`, head unchanged, no `do-not-merge`), and the PR's author is a **different**
account from the merge token's and is one of the allowed identities (`Andy Holst`, `Asimov Agent`), the job
SHALL post an approving review naming itself and then merge. It SHALL NOT approve when the author is the
token's own account (GitHub refuses self-approval) or is any other author, and SHALL NOT approve for any
other merge state.

WHEN the job acts on a review-blocked PR
THEN the approval runs before the merge, and a failure of either is reported rather than silently retried.

#### Scenario: a review-blocked green PR is approved then merged

Given a green, mergeable PR blocked only by a required review, authored by the other allowed identity
When  the job runs with approval enabled
Then  it posts the approval and then merges, in that order.

- **Test:** `tests/test_auto_merge.py::test_a_review_blocked_green_pr_is_approved_then_merged`

#### Scenario: a same-account PR is never self-approved

Given a review-blocked PR whose author is the merge token's own account
When  the job runs
Then  no approval is posted, the PR is deferred, and the comment names GitHub's self-approval rule.

- **Test:** `tests/test_auto_merge.py::test_a_same_account_pr_is_never_self_approved`

#### Scenario: a stranger's PR is not approved

Given a review-blocked PR authored by an account outside the allowlist
When  the job runs
Then  no approval is posted and the deferral names the author.

- **Test:** `tests/test_auto_merge.py::test_a_non_allowlisted_author_is_not_approved`

#### Scenario: other blockers are never approved

Given a PR with merge conflicts, or one behind main
When  the job runs with approval enabled
Then  no approval is posted — only the review state is actionable this way.

- **Test:** `tests/test_auto_merge.py::test_no_approval_for_any_other_blocker`
