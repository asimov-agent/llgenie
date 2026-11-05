# Reviewer finalize (acceptance write-back)

## ADDED Requirements

### Requirement: Idempotent re-invocation

A reviewer finalize step (`scripts/review_finalize.py`) must be idempotent for an already-finalized
verdict: `is_finalized(body, criteria, comment_id)` is `True` exactly when `body` carries `criteria`
ticked acceptance items and every `(proven: comment=…)` on them equals `comment_id`. When `True`,
the finalize step posts no second verdict comment, runs no second PATCH, and returns the existing
`comment_id`.

#### Scenario: re-invoking an already-finalized verdict is a no-op

Given a body whose acceptance section already carries `criteria` ticked boxes, each citing
`(proven: comment=42)`,
and the verdict being re-invoked with the same head sha and criteria count,
when `is_finalized(body, criteria, "42")` is evaluated
then it returns `True`
and the finalize step posts nothing and reuses comment id `42`.

#### Scenario: a partial or empty finalize is never treated as final

Given a body with only some boxes ticked (ticked count < criteria) or a criteria value of 0,
when `is_finalized` is evaluated
then it returns `False`
so the step re-verifies instead of trusting a stale count.

### Requirement: Verification-first "landed"

The finalize step reports "landed" only after a post-write read-back that
`readback_ok(body, criteria, comment_id)` returns `(True, "landed")`, which holds exactly when the
body's ticked-acceptance count equals `criteria` and every `(proven: comment=…)` on a ticked box
equals `comment_id`.

#### Scenario: landed only when the wire matches the verdict

Given a body whose ticked-box count equals `criteria` and all ticked boxes cite `comment=42`,
when `readback_ok(body, criteria, "42")` is evaluated
then it returns `(True, "landed")`
and the finalize step reports landed to the owner.

#### Scenario: a conflicting citation is not landed

Given a body where a ticked box cites a different comment id than the asserted one,
when `readback_ok(body, criteria, comment_id)` is evaluated
then it returns `False` with an `unconfirmed` message
and the step does not report landed.

### Requirement: An unticked read-back is never "landed"

`readback_ok` returns `(False, "unconfirmed, re-read the wire")` when the ticked count differs from
the criteria count, including a body reading 0 ticked against a >0 criteria verdict. The finalize
step never re-posts on such a result.

#### Scenario: 0-ticked read against a 6/6 verdict

Given a body whose acceptance section reads all `- [ ]` (0 ticked) and a verdict with criteria 6,
when `readback_ok(body, 6, comment_id)` is evaluated
then it returns `(False, "unconfirmed, re-read the wire")`
and the step re-reads the wire instead of re-posting the verdict comment.

### Requirement: Head-guarded write-back

The write-back refuses (exit 2) when `head_moved(live_head, judged_head)` is `True` — the live PR
head differs from the verdict's judged sha or is unreadable/empty. A verdict describes one tree.

#### Scenario: a moved head is refused

Given a PR whose live head is `b…` while the verdict was judged at `a…`,
when the write-back checks `head_moved(live_head, judged_head)`
then it returns `True` and the finalize step refuses to PATCH, reporting that the head moved.

#### Scenario: an unchanged head proceeds

Given a PR whose live head equals the verdict's judged sha,
when `head_moved(live_head, judged_head)` is evaluated
then it returns `False` and the write-back may proceed.

### Requirement: No weakening

The guard does not weaken `check_issue_body` / `check-pr-acceptance` and preserves #1644 seam
semantics: the only mutation is the seam's single PATCH, driven by an explicit `proven` set and a
named verdict reference, never by a merge.

#### Scenario: the seam PATCH is the only mutation

Given a finalize that must tick proven acceptance items,
when it writes,
then it calls the single `acceptance_writeback` PATCH with an explicit `proven` set and a named
verdict reference,
and no other issue-body mutation occurs.
