# Reviewer finalize is idempotent and verification-first (#1808)

`scripts/review_finalize.py` wraps the acceptance write-back seam (#1644) in a guarded,
verification-first finalize step, fixing a measured defect on #1806 where the finalize path posted
three identical `COMMENTED` reviews and three identical verdict comments, and first reported
finalization as unconfirmed.

The new guard:

- **Idempotent** — `is_finalized` recognises an already-finalized body (criteria ticked boxes all
  citing the same `comment=<id>`) and the step reuses that id: no second comment, no second PATCH.
- **Verification-first** — "landed" is reported only after a read-back asserts the ticked-box count
  equals the criteria count and every `(proven: comment=…)` equals the single verdict comment id.
- **0-ticked read is never "landed"** — an unticked read against a >0 criteria verdict returns
  `unconfirmed, re-read the wire`, never a re-post.
- **Head-guarded** — the write-back refuses (exit 2) when the live PR head moved past the verdict's
  judged sha.

Bounding: no gate is weakened (`check_issue_body` / `check-pr-acceptance`), and the write remains the
seam's single PATCH driven by an explicit `proven` set and a named verdict reference.

Evidence: full hermetic suite passes (17 tests incl. the write-back suite), `make lint` and
`make ci-openspec` green; the OpenSpec change `review-finalize-idempotent` is validated.
