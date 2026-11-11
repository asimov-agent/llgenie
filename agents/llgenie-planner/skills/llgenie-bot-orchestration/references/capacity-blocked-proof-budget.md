# Proof run cancelled by its OWN timeout = capacity-blocked, not regression

When a lane reports a proof/build run as "SETTLED CANCELLED, NOT green", do not accept the summary — read the run and its jobs:

```bash
gh api repos/<repo>/actions/runs/<id> --jq '.status,.conclusion,.created_at,.updated_at'
gh api repos/<repo>/actions/runs/<id>/jobs --jq '[.jobs[]|"\(.name)=\(.conclusion//"running")"]'
```

- `conclusion=cancelled` with `updated_at - created_at` ≈ the job's own `timeout-minutes` and a build cell `cancelled` while `guard`/`matrix` are `success` => the cell exhausted its budget mid-compile. That is a **capacity** fact, not a verdict on the code, and not a regression from the PR under test.
- Distinguish from a human/queue cancel: a timeout cancel is preceded by ~the full budget elapsing and only the heavy cell dying; a queue-clear cancel kills jobs early across the board and is an incident (never cancel a live run to "clear the queue").

## Rule: no blind redispatch of an expensive blocked proof

A second dead >4h attempt on the SAME build class means the lane must NOT blind-dispatch a third one. Verify the class is unchanged (its code fix already merged and untouched, e.g. the vendored-Rust/ROCm-triton build fix) — if so the block is proof capacity, and spending another multi-hour run is a **budget decision that belongs to the owner**, not the planner and not the lane.

## Raising a timeout is a capacity change, not a gate weaken

When the owner budgets more time: raise `timeout-minutes` for the affected cell only (parameterise by engine/variant so other cells keep the smaller budget) or the whole job if that is cleaner; do NOT touch the build steps themselves and do NOT relax any correctness check. One PR for the timeout, ready-for-review, owner merges. Then re-dispatch exactly ONE proof run.

Boxes tick only on a real `completed/success` run at the head — a `cancelled` run ticks nothing, and "green locally" or "guard+matrix passed" is not the cell passing.

## Escalate, don't rule

The planner escalates the budget question to the owner (a clarify with the measured facts + the concrete options) and records the ruling on the issue as a comment, so the decision exists for the next reader and not only in a DM.
