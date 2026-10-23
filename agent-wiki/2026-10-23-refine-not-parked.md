# 2026-10-23 — a refine keeps the issue queueable (#522)

**Issue:** [#522](https://github.com/asimov-agent/llgenie/issues/522) · **PR:** the PR that closes it

## What was wrong

`DECIDED_LABELS = ("agent:refined", "agent:closed")` and both pickers skip a decided issue. The refine verdict
labels the issue `agent:refined`, so the verdict that improves an issue also removed it from the only queue that
implements anything — a refine was a one-way door. Measured on `main` (`333344c`): 15 open `agent:implement`,
1 `agent:ready`, **3 open `agent:refined`** (parked, not queued), with #399 as the recorded example.

## What changed

- `DECIDED_LABELS = ("agent:closed",)`; `REFINED_LABEL` is a marker ("a restatement exists").
- The refine verdict adds `agent:refined` **and** `agent:ready` when the issue carries no queue label, so the
  improved specification is actually in the queue.
- A second refine of an already-refined issue is refused loudly instead of repeating the comment.
- README and the module docstrings now say "only a close is a decision".

## Verified

- `pytest tests/test_issue_implementer.py tests/test_issue_refiner.py tests/test_bot_claims.py` in
  `llgenie/test:latest` → **74 passed**, including a refined issue being picked, the refine queueing it, and a
  closed issue still skipped before any thread read.
- Three fixtures that pinned the old behaviour now encode the fix (`agent:closed` for "decided").
- `make lint`, `make check-docs`, `make check-workflows`, `make check-wiring`,
  `make openspec-validate NAME=refine-not-parked`, `make openspec-tasks-check` → green.
- `make test-unit` runs in the PR's checks.

## Next

The duplicate-cleaner bot (4×/day, never touching `agent:implement`) is a separate change on top of this one:
with the refine marker no longer parking issues, a dedupe label can safely be a marker too.
