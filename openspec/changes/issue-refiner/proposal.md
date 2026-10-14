# A refiner for the not-yet-implemented backlog, on the implementer's spare capacity

## Why

Only the issue the implementer is about to implement ever gets refined. The backlog keeps whatever
quality it had when it was filed: missing acceptance criteria, scope settled in an old comment,
duplicates and already-done issues that an agent only discovers by spending a branch and a run.

## What changes

- `scripts/issue_refiner.py`: `count` (its own daily budget via the `agent:refined` label), `pick`
  (spare capacity + the oldest eligible issue), `apply` (ONE comment + `agent:refined`).
- **Spare capacity as the trigger, in code**: `pick` refuses while the implementer still has a PR
  slot, so the bots never race and this one never competes for the 3/day PR cap (#107: the decision
  is not a CI `if:`).
- Eligibility skips decided, claimed-for-implementation and already-PR'd issues.
- The agent **reviews** (acceptance criteria, scope, surfaces, open questions named as questions) and
  the outcome is one comment plus a label: no branch, no PR, no issue-body edit.
- `issue-refiner.yml`: schedule + owner-guarded dispatch, concurrency 1, in the agent image.

## Impact

Issues reach the implementer already implementable, one per run, without consuming its slots or
opening a single PR. An issue is reviewed at most once (the label), and a human still decides
anything the review leaves open.
