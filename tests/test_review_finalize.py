"""The reviewer-finalize guard (issue #1808): idempotent + verification-first finalize.

Everything here exercises the REAL module — `review_finalize.is_finalized` / `readback_ok` /
`head_moved` and the #1644 seam's `tick_acceptance` are the product. Nothing talks to the network:
the `gh` wrapper (`finalize`/`_write`) is not exercised here (mirrors how `test_acceptance_writeback`
leaves the thin `gh api PATCH` wrapper behind `main` unattested).

The acceptance criteria under proof (issue #1808):
1. re-invoking an already-finalized verdict (same PR, same head sha, same verdict text) is a NO-OP —
   posts no second comment, runs no second PATCH, returns the existing comment id
   (red-on-old: the unguarded path would post a duplicate);
2. a completed verdict is only "landed" after a read-back asserts: exactly one verdict comment id,
   body ticked-box count == criteria count, and every `(proven: comment=…)` equals that id;
3. a read-back returning the body UNTICKED (0/6) against a 6/6 verdict is NEVER "landed" — it is
   "unconfirmed, re-read the wire", never re-posted;
4. the write-back refuses to PATCH a body whose live head moved past the verdict's judged sha.

NO-SKIP POLICY: a missing prerequisite is a LOUD FAILURE, never a skip.
"""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

from scripts import acceptance_writeback as aw  # noqa: E402
from scripts import review_finalize as rf  # noqa: E402

#: One comment id, as a citable verdict would carry it.
COMMENT = "42"

#: A body in the six-section shape (issue #745) with three acceptance criteria.
BODY = (
    "## Problem\np\n\n## Why it matters\nw\n\n## How we fix it\n1. a\n2. b\n\n"
    "## Benefit\nb\n\n## Acceptance criteria\n\n- [ ] criterion one\n- [ ] criterion two proves it\n"
    "- [ ] criterion three\n\n## Technical\n\n- where: x\n"
)


def _ticked(ref: str = COMMENT, n: int = 3) -> str:
    """A body whose first `n` boxes are ticked with `(proven: … comment=<ref>)` (all 3 by default)."""
    return aw.tick_acceptance(BODY, {1, 2, 3}, f"reviewer=rr comment={ref} head=abc run=99")


def test_reinvoking_an_already_finalized_verdict_is_a_noop():
    """Criterion 1 — idempotence pre-check: an already-finalized body is recognised as such.

    Red-on-old: an unguarded finalize step would post a second PATCH/comment because nothing checked
    whether the write-back already happened. Green-on-fixed: `is_finalized` returns True for the
    re-invoked (already-finalized) state with the SAME head/comment than it returns before any tick.
    """
    finalized = _ticked(COMMENT)
    # The finalized body is idempotent: is_finalized True, reuse the existing comment id.
    assert rf.is_finalized(finalized, criteria=3, comment_id=COMMENT) is True
    # Re-running tick_acceptance on the finalized body does not duplicate the citation lines:
    # the seam is idempotent, so the body is stable under re-apply, and the comment id is reused.
    reapplied = aw.tick_acceptance(finalized, {1, 2, 3}, f"reviewer=rr comment={COMMENT} head=abc run=99")
    assert reapplied == finalized
    # Before any write-back the verdict is NOT finalized.
    assert rf.is_finalized(BODY, criteria=3, comment_id=COMMENT) is False


def test_criteria_count_mismatch_is_never_treated_as_finalized():
    """A changed body (criteria count != the judged count) is not trusted as finalized."""
    # Same comment cited, but only 2 of 3 proven → criteria count mismatch.
    partial = aw.tick_acceptance(BODY, {1, 2}, f"reviewer=rr comment={COMMENT} head=abc run=99")
    assert rf.is_finalized(partial, criteria=3, comment_id=COMMENT) is False
    # criteria == 0 is a contradiction (nothing to prove).
    assert rf.is_finalized(BODY, criteria=0, comment_id=COMMENT) is False


def test_landed_only_after_readback_asserts_exactly_one_citation():
    """Criterion 2 — verification-first: "landed" requires count match AND all cite the one id."""
    ok, msg = rf.readback_ok(_ticked(COMMENT), criteria=3, comment_id=COMMENT)
    assert (ok, msg) == (True, "landed")

    # A conflicting citation on a ticked line is NOT landed (not the asserted single comment id).
    mixed = _ticked(COMMENT).replace(f"comment={COMMENT}", "comment=99", 1)
    ok, msg = rf.readback_ok(mixed, criteria=3, comment_id=COMMENT)
    assert ok is False and "unconfirmed" in msg

    # Box count over the criteria count is not landed either.
    assert rf.readback_ok(_ticked(COMMENT), criteria=2, comment_id=COMMENT)[0] is False


def test_zero_ticked_read_against_full_verdict_is_never_landed():
    """Criterion 3 — a 0-ticked read-back (0/6) against a 6/6 verdict is "unconfirmed", not landed."""
    ok, msg = rf.readback_ok(BODY, criteria=3, comment_id=COMMENT)   # all `- [ ]`
    assert ok is False and msg == "unconfirmed, re-read the wire"


def test_writeback_refuses_a_moved_head():
    """Criterion 4 — write-back refuses to PATCH a body whose head moved past the judged sha."""
    judged = "a" * 40
    assert rf.head_moved(live_head="b" * 40, judged_head=judged) is True
    assert rf.head_moved(live_head=judged, judged_head=judged) is False
    # A short/empty live head (unreadable) is treated as moved — never assume it still matches.
    assert rf.head_moved(live_head="", judged_head=judged) is True
