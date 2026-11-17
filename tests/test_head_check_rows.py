"""tests/test_head_check_rows.py — the shared supersede collapse for a head's check-run rows.

Issue #2885: GitHub keeps a check-run row for EVERY run attached to a commit, and
`check-runs?filter=latest` collapses only re-run attempts of the same run id (measured at PR #2882
head `585b03dd74`: three `scope` rows from three separate runs, all returned). `scripts/ci_verdict.py`
and `scripts/auto_merge.py` therefore share ONE client-side collapse: within a (job name, workflow
file) group, the newest CONCLUDED row governs the head, and strictly-older concluded rows are
superseded. These tests pin the semantics directly, so both readers can never drift apart.
"""

from __future__ import annotations

import inspect

from scripts import auto_merge as am
from scripts import ci_verdict as cv
from scripts import head_check_rows as hcr

BLOCK = frozenset({"failure"})
SCOPE = ".github/workflows/scope.yml"
OTHER = ".github/workflows/scope-nightly.yml"


def _row(rid: int, name: str, conclusion: "str | None", started: str, file: str) -> dict:
    row = {"id": rid, "name": name, "details_url": f"https://github.com/o/r/actions/runs/{1000 + rid}"}
    if conclusion is not None:
        row["conclusion"] = conclusion
        row["status"] = "completed"
    else:
        row["status"] = "in_progress"
    if started is not None:
        row["started_at"] = started
    row["_file"] = file
    return row


def _files(rows: list[dict]):
    return lambda row: row.get("_file") or ""


def test_an_older_red_replaced_by_a_newer_green_of_the_same_file_is_superseded():
    # Given the measured shape: a dead 08:00 `scope` failure, a newer 09:00 `scope` success, same file
    rows = [_row(1, "scope", "failure", "2026-11-17T08:00:00Z", SCOPE),
            _row(2, "scope", "success", "2026-11-17T09:00:00Z", SCOPE)]

    # When  the collapse runs
    sup = hcr.superseded_ids(rows, BLOCK, _files(rows))

    # Then  only the old red is superseded; the green is not (it IS the head's newest word)
    assert sup == {1}, sup


def test_the_newest_concluded_row_is_never_superseded_even_when_it_is_red():
    # Given the same job failing twice through the same file
    rows = [_row(1, "scope", "failure", "2026-11-17T08:00:00Z", SCOPE),
            _row(2, "scope", "failure", "2026-11-17T09:00:00Z", SCOPE)]

    sup = hcr.superseded_ids(rows, BLOCK, _files(rows))

    # Then  collapse NEVER erases red: the newest failure survives as the blocker
    assert sup == {1}, sup


def test_an_unconcluded_newer_row_neither_supersedes_nor_clears_the_red():
    # Given the old failure and a newer run that has not concluded
    rows = [_row(1, "scope", "failure", "2026-11-17T08:00:00Z", SCOPE),
            _row(2, "scope", None, "2026-11-17T09:00:00Z", SCOPE)]

    sup = hcr.superseded_ids(rows, BLOCK, _files(rows))

    # Then  the absence of red is not a pass: the concluded red stands
    assert sup == set(), sup


def test_a_newer_row_from_a_different_workflow_file_does_not_supersede():
    # Given the same job NAME posted by two DIFFERENT workflow files
    rows = [_row(1, "scope", "failure", "2026-11-17T08:00:00Z", SCOPE),
            _row(2, "scope", "success", "2026-11-17T09:00:00Z", OTHER)]

    sup = hcr.superseded_ids(rows, BLOCK, _files(rows))

    # Then  the groups are separate and the red stands
    assert sup == set(), sup


def test_a_row_whose_workflow_file_cannot_be_resolved_is_never_superseded():
    # Given a red whose app identity cannot be resolved to a workflow file ("" from the resolver)
    rows = [_row(1, "scope", "failure", "2026-11-17T08:00:00Z", ""),
            _row(2, "scope", "success", "2026-11-17T09:00:00Z", SCOPE)]

    sup = hcr.superseded_ids(rows, BLOCK, _files(rows))

    # Then  unknown identity keeps the red in play — no clear on an unresolvable read
    assert sup == set(), sup


def test_rows_are_ordered_by_started_at_with_id_as_the_tiebreaker():
    # Given same-name rows with an EQUAL started_at (the documented same-timestamp rerun)
    rows = [_row(11, "scope", "failure", "2026-11-17T09:00:00Z", SCOPE),
            _row(12, "scope", "success", "2026-11-17T09:00:00Z", SCOPE)]

    sup = hcr.superseded_ids(rows, BLOCK, _files(rows))

    # Then  the higher row id is the newer attempt; the lower one is superseded
    assert sup == {11}, sup

    # And   with no usable timestamps at all and no ids, nothing is ever called superseded
    mute = [{"name": "scope", "conclusion": "failure"}, {"name": "scope", "conclusion": "success"}]
    assert hcr.superseded_ids(mute, BLOCK, lambda r: SCOPE) == set()

    # And   completed_at carries the ordering when started_at is absent
    rows = [{"id": 1, "name": "scope", "conclusion": "failure", "completed_at": "2026-11-17T08:00:00Z"},
            {"id": 2, "name": "scope", "conclusion": "success", "completed_at": "2026-11-17T09:00:00Z"}]
    assert hcr.superseded_ids(rows, BLOCK, lambda r: SCOPE) == {1}


def test_the_collapse_resolves_only_groups_that_hold_a_blocking_row():
    # Given a fully green head beside one red trigger row
    seen: list[str] = []

    def counting_file_of(row: dict) -> str:
        seen.append(str(row.get("name")))
        return str(row.get("_file") or "")

    rows = [_row(1, "linux / unit", "success", "2026-11-17T08:00:00Z", ".github/workflows/ci.yml"),
            _row(2, "linux / lint", "success", "2026-11-17T08:00:00Z", ".github/workflows/ci.yml"),
            _row(3, "trigger", "failure", "2026-11-17T08:30:00Z",
                 ".github/workflows/engine-build-pr-trigger.yml")]

    sup = hcr.superseded_ids(rows, BLOCK, counting_file_of)

    # Then  the collapse paid for the red's group only — green-only names were never resolved,
    # so the verdict's existing one-resolve-per-red cost (and its fake-API fixtures) hold.
    assert sup == set(), sup
    assert set(seen) == {"trigger"}, seen


def test_both_readers_share_one_block_set_and_one_collapse():
    """#2885 AC-3: `auto_merge.failing_checks` defers on a row exactly when `ci_verdict`'s unjudged
    scan would call it a red — same block set, same collapse call, one implementation."""

    assert cv.BLOCKING_CONCLUSIONS == am.RED_CONCLUSIONS, (cv.BLOCKING_CONCLUSIONS, am.RED_CONCLUSIONS)
    v_src = inspect.getsource(cv.unjudged_reds)
    m_src = inspect.getsource(am.failing_checks)
    for src in (v_src, m_src):
        assert "head_check_rows.superseded_ids" in src, src[:200]
    assert hcr.superseded_ids.__module__.endswith("head_check_rows")
