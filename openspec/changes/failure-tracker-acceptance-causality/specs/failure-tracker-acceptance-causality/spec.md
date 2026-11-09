# Failure-tracker acceptance causability

## ADDED Requirements

### Requirement: A filed tracker's acceptance names the cause class, the recurrence and a negative control

`run-failure-reactor`'s generic (non-pins-publish) `issue_body()` MUST name in `## Acceptance
criteria`, for every filed tracker: the **failure class** (the mechanism in the failing step's
logged error in the Technical tail, not the job name), the **recurrence** the fix prevents (a
negative-control test that FAILS on the pre-fix tree and PASSES on the fix), and a **negative
control** — the failing job's `databaseId`, which the guard must fire on. The
green-locally / green-on-the-same-job / `closes #<n>` boxes MUST stay but count as supporting
evidence only. The pins-publish branch keeps its three publish-specific boxes unchanged. The
template MUST still pass `scripts/issue_body.py::missing` (the six-section gate).

#### Scenario: a filed tracker names a class a reviewer can hold to account

Given a failed CI run with a failing step and a job `databaseId`, when the reactor files the
generic (non-pins-publish) tracker, then its `## Acceptance criteria` names the cause class from
the failing step's logged error and the failing job's `databaseId` as the negative control, so a
symptom patch that only re-runs one job cannot tick every box.

#### Scenario: the acceptance is a negative control that fails on the pre-fix template

Given the acceptance template before this change, when the new negative-control test runs against
it, then it FAILS (the generic three-line list is no longer the whole acceptance), and when it runs
against the change, it PASSES.
