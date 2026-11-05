# Tasks — reviewer finalize is idempotent and verification-first

- [x] Add `scripts/review_finalize.py` — a guarded wrap over the #1644 write-back seam:
  `is_finalized`, `readback_ok`, `head_moved` pure core + thin `gh` `finalize`/`check` CLI.
- [x] Add `tests/test_review_finalize.py` — red-on-old (an unguarded replay posts a second PATCH) /
  green-on-fixed (a replay is a no-op returning the existing comment id; a 0-ticked read against a
  >0 verdict is never "landed").
- [x] Add change-note trio (agent-wiki + docs/changes.d fragment + CHANGES.md) carrying `#1808`.
- [x] Validate: `make openspec-validate NAME=review-finalize-idempotent` and `make ci-openspec` pass.
- [x] Full hermetic suite passes (no regression to `acceptance_writeback` / `check-pr-acceptance`).
