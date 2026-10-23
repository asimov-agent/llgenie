# auto-merge-wait-for-approval

## ADDED Requirements

### Requirement: The job waits for the approval to take effect

After posting an approving review, the auto-merge job SHALL re-read the pull request, bounded, until
`mergeStateStatus` reflects the approval (`CLEAN`), and SHALL decide the merge from that read. A single
immediate read SHALL NOT be treated as the final answer.

WHEN the job approves a review-blocked green PR
THEN it polls the PR state and merges as soon as it is CLEAN, without using `--admin`.

#### Scenario: a state that settles after two reads is merged

Given a PR whose `mergeStateStatus` stays `BLOCKED` for two reads after the approval and is `CLEAN` afterwards
When  the job runs with review clearance enabled
Then  it merges on the polled read and the merge carries no `--admin`.

- **Test:** `tests/test_auto_merge.py::test_the_approval_is_waited_for_before_deciding`

### Requirement: A PR that never settles defers naming the real reason

When the approval lands but the PR does not become mergeable within the bounded wait, the deferral comment
SHALL say so and name the last observed state, and SHALL NOT render an empty or `None` reason.

WHEN the PR stays `BLOCKED` for every read and the admin merge is refused too
THEN the run exits 0 and the comment states the approval landed and the state it stayed stuck in.

#### Scenario: the deferral never says None

Given a PR that stays `BLOCKED` however long the job waits, and a merge GitHub refuses
When  the job runs
Then  the comment contains "did not become mergeable within the wait" and does not contain "None;".

- **Test:** `tests/test_auto_merge.py::test_a_pr_that_never_settles_defers_naming_the_real_reason`
