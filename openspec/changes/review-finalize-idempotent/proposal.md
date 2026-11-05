# Reviewer finalize is idempotent and verification-first

## Problem

A completed reviewer verdict can be reported "landed" without having been verified, and the
reviewer-finalize step is not idempotent. Measured on #1806 (`feat(issue-refiner)`, head
`a5b78cca`, verdict 6/6 proven): the finalize path posted three identical `COMMENTED` review
submissions (5789756625/5789757027/5789757603) and three identical verdict comments
(6665614496/6665628482/6665629655), and first reported finalization as UNCONFIRMED before a later
read confirmed the write-back. `acceptance_writeback.py` (the #1644 seam) is deterministic — the
defect is the caller, which has nothing guarding a second post and nothing verifying a first one
before declaring success.

## Why it matters

The review verdict is load-bearing state (fleet rule 1 / issue-body seam #1644): a COMMENTED verdict
plus `--proven` write-back is what ticks an issue's acceptance boxes, gates downstream CI, and
closes the owner's delegation loop. A non-idempotent finalize that reports before read-back buries
the board under N identical verdict comments, risks two write-backs racing to PATCH the same body,
and produces self-contradictory read-backs ("6/6 proven" while boxes read unticked) that a reviewer
cannot distinguish from a genuine failure without re-reading the wire.

## How we fix it

`scripts/review_finalize.py` wraps the existing seam in a guarded, verification-first finalize step:

1. **Idempotent pre-check** — before posting anything or running a write-back, count the ticked
   acceptance boxes on the live body at the judged head sha. If every box already carries
   `(proven: comment=<id>)` at the criteria count, the verdict is already-finalized: reuse that
   comment id, post nothing, PATCH nothing.
2. **Verification-first** — "landed" is only reported after a read-back asserts: exactly one verdict
   comment id, the body's ticked-box count == the criteria count, and every `(proven: comment=…)`
   equals that single id.
3. **0-ticked read is never "landed"** — a body reading unticked against a >0 criteria verdict is
   reported `unconfirmed, re-read the wire`, never re-posted.
4. **Head-guarded** — the write-back refuses to PATCH a body whose live head moved past the verdict's
   judged sha (a verdict describes one tree).

Bounding: this does not weaken `check_issue_body` / `check-pr-acceptance` and keeps the #1644 seam
semantics — the write itself is still the seam's single PATCH, refused rather than mutated when the
read-back cannot confirm.

## Benefit

A replayed or retried finalize can no longer duplicate the verdict comment or race-approve a
mis-read state. The owner sees one citable verdict per head sha and a "landed" report that provably
matches the wire (single comment id, box count == criteria count, cite == comment id).

## Open questions

- The finalize wrapper is invoked by the reviewer lane's procedure; exact CLI ergonomics may refine
  with adoption, but the pure core (`is_finalized`, `readback_ok`, `head_moved`) is the committed
  contract.
