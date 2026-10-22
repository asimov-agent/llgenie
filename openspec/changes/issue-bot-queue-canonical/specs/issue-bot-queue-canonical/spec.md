# issue-bot-queue-canonical

## ADDED Requirements

### Requirement: A close verdict queues the canonical issue it cites

When the issue-implementer closes an issue as a duplicate, superseded or already-implemented, it SHALL
queue every issue reference (`#<n>`) cited in its `EVIDENCE:`/`REASON:` blocks that is open and carries no
agent label, by adding `agent:implement`. The picker lists only `agent:implement` / `agent:ready`, so
without this step the canonical issue stays invisible and the defect is never implemented.

WHEN a close verdict cites an open, unlabelled issue
THEN that issue is labelled `agent:implement` before the run ends.

#### Scenario: the cited canonical issue is queued

Given an open issue `#399` with no agent label
And  a close verdict for `#440` whose evidence cites `#399`
When  the verdict is applied
Then  `#440` is closed and labelled `agent:closed`
And  `#399` is labelled `agent:implement`.

- **Test:** `tests/test_issue_implementer.py::test_a_close_queues_the_canonical_issue_it_cites`

#### Scenario: a closed, decided or already-queued reference is left alone

Given `#254` is closed, `#466` already carries `agent:implement`, and `#470` carries `agent:refined`
And  a close verdict cites all three plus the issue being closed
When  the verdict is applied
Then  no edit is made outside the issue being closed.

- **Test:** `tests/test_issue_implementer.py::test_a_close_leaves_a_closed_decided_or_already_queued_reference_alone`

### Requirement: A reference that is not a readable issue never fails the close

A cited number that `gh issue view` cannot read (a PR number, a typo, a deleted issue) SHALL be printed
and skipped; the close itself SHALL still succeed, because the close is the primary action.

WHEN a close verdict cites a number that is not an open issue
THEN the close proceeds, nothing outside the issue is edited, and the run exits 0.

#### Scenario: a PR number and a typo are skipped, the close still happens

Given a close verdict citing `#999` (a PR) and `#1234` (does not exist)
When  the verdict is applied
Then  `#440` is closed and no other issue is edited.

- **Test:** `tests/test_issue_implementer.py::test_a_close_citing_a_pr_number_or_typo_queues_nothing_and_still_closes`

#### Scenario: a dry run reports the queueing and mutates nothing

Given a close verdict that would queue `#399`
When  the verdict is applied with `--dry`
Then  no comment, close or label request is made, and the queueing decision is printed.

- **Test:** `tests/test_issue_implementer.py::test_a_dry_close_would_queue_and_write_nothing`
