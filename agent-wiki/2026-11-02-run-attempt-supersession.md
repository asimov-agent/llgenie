# Run-attempt-aware supersession (#1422, #1250 Finding A)

2026-11-02. A re-run of a GitHub Actions workflow keeps the **same run id and `created_at`** and bumps
only `run_attempt`. Supersession that orders strictly by `created_at` therefore cannot see a re-run —
it read a cancelled attempt-1 as the head's final conclusion while a live attempt-2 owned the head.

Two consumers now read `run_attempt`:

- **`scripts/ci_verdict.py` `superseding_run()`** — a same-id run with a higher `run_attempt` wins
  the same-id case (before any later-`created_at` run), so a bumped-attempt re-run supersedes the
  attempt it replaced and the verdict is neutral, never `success`.
- **`scripts/ci_requeue.py` `plan()`** — the cancellation healer tracks the max `run_attempt` per
  (workflow, branch); a cancelled attempt whose same id has been re-run at a higher attempt is
  skipped as `superseded: a newer attempt of this run is on this branch`, never requeued (requeuing
  it would re-run the very attempt the newer attempt already replaced).

Measured at main `279fc0d6`. Guard-proofed: both new tests red against the pre-fix logic, green after
the fix. Issue: #1422. Related: #1250.
