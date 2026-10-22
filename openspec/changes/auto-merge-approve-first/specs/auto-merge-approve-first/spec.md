# auto-merge-approve-first

## ADDED Requirements

### Requirement: A review-blocked green PR is approved by the other identity, then merged

When a green PR is blocked only by a required review (`mergeable: MERGEABLE`, `mergeStateStatus: BLOCKED`,
`reviewDecision: REVIEW_REQUIRED`), the auto-merge job SHALL approve it as the identity that is NOT its
author and SHALL then merge the validated head with a plain `gh pr merge --squash --match-head-commit`. The
admin bypass SHALL NOT be the first answer, because GitHub refuses it wherever the review rule is enforced
for admins.

WHEN a green PR is review-blocked and the merge token is not its author
THEN the job approves, re-reads the PR, and merges it without `--admin`.

#### Scenario: approve then merge, in that order, without the admin bypass

Given a green PR authored by `andyholst` and a merge token belonging to `asimov-agent`
When  the job runs with review clearance enabled
Then  it posts an approving review before the merge, and the merge carries no `--admin`.

- **Test:** `tests/test_auto_merge.py::test_a_review_blocked_green_pr_is_approved_by_the_other_identity_then_merged`

### Requirement: A self-authored review block falls back to the admin bypass, then defers

When the PR's author IS the merge token's account, no approval is possible (GitHub refuses a self-approval).
The job SHALL try the admin bypass; if that is refused too, it SHALL post the reason on the PR and exit 0,
never a bare red run.

WHEN the author is the merge token's account and the admin merge is refused
THEN the run exits 0 and the PR carries one comment naming the refusal.

#### Scenario: no self-approval, admin fallback

Given a review-blocked PR authored by `asimov-agent` and the same account's merge token
When  the job runs
Then  no approving review is posted and the merge uses `--admin`.

- **Test:** `tests/test_auto_merge.py::test_a_same_account_pr_falls_back_to_admin`

#### Scenario: a refused admin merge is a deferral with the reason on the PR

Given the admin merge is refused by GitHub
When  the job runs
Then  it exits 0 and posts a comment saying the admin merge was refused.

- **Test:** `tests/test_auto_merge.py::test_a_refused_merge_defers_with_the_reason_on_the_pr`

### Requirement: An optional approver token supplies the second identity

An optional `APPROVER_TOKEN` secret SHALL be used for the approval when the PR author is the merge token's
own account. The value SHALL travel in the environment only, never on a command line or in argv.

WHEN `APPROVER_TOKEN` belongs to the other allowed identity
THEN the approval is posted with that token and the merge is not the admin bypass.

#### Scenario: a bot PR is approved with the second identity

Given a review-blocked PR authored by `asimov-agent` and an `APPROVER_TOKEN` for `andyholst`
When  the job runs
Then  the approving review is posted with that token and the merge carries no `--admin`
And  the token never appears in any argv.

- **Test:** `tests/test_auto_merge.py::test_a_same_account_pr_is_approved_with_the_approver_token`
