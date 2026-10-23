# refine-not-parked

## ADDED Requirements

### Requirement: A refined issue stays queueable

`agent:refined` SHALL be a marker that a restatement exists, never a decision that blocks the picker. The
pickers SHALL skip only `agent:closed`. A refine verdict SHALL add `agent:refined` and, when the issue carries
no queue label, `agent:ready`.

WHEN a refine verdict is applied
THEN the issue is queueable: it carries a queue label, no `agent:closed`, and the next dispatch can pick it.

#### Scenario: a refined issue is picked

Given an open issue labelled `agent:implement` and `agent:refined`, with no live claim
When  the implementer's picker runs
Then  it returns that issue instead of skipping it.

- **Test:** `tests/test_issue_implementer.py::test_a_refined_issue_is_still_picked`

#### Scenario: the refine queues an unqueued issue

Given an open issue with no agent label
When  a refine verdict is applied
Then  it is commented on, labelled `agent:refined`, and also labelled `agent:ready`.

- **Test:** `tests/test_issue_implementer.py::test_a_refine_posts_one_comment_and_labels_it_without_a_pr`

### Requirement: Only a close is a decision

`DECIDED_LABELS` SHALL contain `agent:closed` alone, so a close still ends an issue's life in the picker and a
close cannot loop, while a refined canonical reference a close cites is still queued.

WHEN the picker meets an issue labelled `agent:closed`
THEN it skips it before reading the thread.

#### Scenario: a closed issue is skipped without a thread read

Given a candidate labelled `agent:closed`
When  the picker runs
Then  it is skipped and no thread read is spent on it.

- **Test:** `tests/test_issue_implementer.py::test_a_decided_issue_is_still_skipped_before_any_thread_is_read`

#### Scenario: a refined but unqueued canonical is queued

Given a close verdict citing an open issue labelled `agent:refined` with no queue label
When  the verdict is applied
Then  that canonical issue receives `agent:implement`, because the work is still real and still open.

- **Test:** `tests/test_issue_implementer.py::test_a_refined_but_unqueued_canonical_is_queued`

### Requirement: A second refine is refused

An issue that already carries `agent:refined` SHALL NOT be refined again: the run SHALL fail loudly rather
than repeat the comment.

WHEN a refine verdict is applied to an issue that already carries `agent:refined`
THEN the run exits non-zero, naming the label, and posts nothing.

#### Scenario: a second refine is refused

Given an issue that already carries `agent:refined`
When  a refine verdict is applied to it again
Then  the run exits non-zero naming the label, and posts no comment.

- **Test:** `tests/test_issue_implementer.py::test_a_second_refine_of_an_already_refined_issue_is_refused`
