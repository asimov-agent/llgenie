#!/usr/bin/env python3
"""Collapse a head's check-run rows to the newest concluded row per (job name, workflow file).

Issue #2885, measured 2026-11-17 at PR #2882 head `585b03dd74`: three `scope` rows coexisted at
the same head (two `success`, one `failure` from the since-cleared run 44046649110) and the
verdict posted `conclusion=failure` naming only the dead row, because every red row EVER posted
at the head was read as blocking. GitHub's `filter=latest` does not fix this: measured, it still
returns all three rows, because only re-runs of the SAME run id collapse — separate runs of the
same workflow file mint new check-run ids. So the collapse must happen here, client-side.

The rule both readers share (`scripts/ci_verdict.py::unjudged_reds`,
`scripts/auto_merge.py::failing_checks` — one implementation, never two):

- A group is (job name, workflow file). Within a group, only the NEWEST CONCLUDED row governs;
  every strictly-older concluded row is SUPERSEDED and never blocks.
- "Concluded" means a non-empty `conclusion` (a queued/in_progress row has none): an unfinished
  run neither supersedes an older red nor is superseded — the absence of red is not a pass.
- "Newest" is `started_at` (ISO-Z, so lexicographic), tie-broken by row id; a row with no usable
  timestamp AND no numeric id is never superseded (conservative when a fixture is silent).
- A row whose workflow file cannot be resolved (empty path) is never superseded and never
  supersedes: the group identity is unknown, so #1250's "any red at the head" stays in force.

This module resolves nothing itself: it takes the resolver `file_of(row)` from the caller (the
CI lane's own `workflow_of`, the bot's own `gh` read) and calls it ONLY for rows whose job name
has a blocking candidate, so the collapse never pays for the whole green head.
"""

from __future__ import annotations

from typing import Callable

#: What makes a row conclude this module's group: a non-empty conclusion string.
_CONCLUDED = "concluded"


def _row_id(row: dict) -> int:
    try:
        return int(str(row.get("id")))
    except (TypeError, ValueError):
        return -1


def row_sort_id(row: dict) -> int:
    """The row's group identity / ordering tiebreaker, as this module reads it (-1: none)."""
    return _row_id(row)


def _row_time(row: dict) -> str:
    """The row's ordering time: `started_at`, falling back to `completed_at` (ISO-Z strings)."""
    return str(row.get("started_at") or row.get("completed_at") or "")


def _concluded(row: dict) -> bool:
    return bool(row.get("conclusion"))


def superseded_ids(rows: list[dict], blocking: frozenset[str],
                   file_of: Callable[[dict], str]) -> set[int]:
    """The ids of rows that their group's newest concluded row has replaced.

    `rows` is the head's full check-run listing. `blocking` is the caller's block set
    (`ci_verdict.BLOCKING_CONCLUSIONS` == `auto_merge.RED_CONCLUSIONS`, pinned equal by
    `tests/test_ci_verdict.py`) — it names which rows NEED the collapse; only groups that hold
    at least one blocking row get a `file_of` call, on the rows sharing that job name.

    A returned id is a row that a strictly-newer concluded row with the same (name, workflow
    file) has replaced. The newest concluded row itself is NEVER returned, whatever its
    conclusion: it is what the head now says, and the caller applies its own filters to it.
    """
    resolved: dict[int, str] = {}

    def file_for(row: dict) -> str:
        rid = _row_id(row)
        if rid not in resolved:
            resolved[rid] = str(file_of(row) or "")
        return resolved[rid]

    red_names = {str(row.get("name") or "") for row in rows
                 if str(row.get("conclusion") or "") in blocking}
    candidates = [row for row in rows if str(row.get("name") or "") in red_names]

    groups: dict[tuple[str, str], list[dict]] = {}
    for row in candidates:
        path = file_for(row)
        if not path:
            continue  # identity unknown: never superseded, never a superseder (conservative)
        groups.setdefault((str(row.get("name") or ""), path), []).append(row)

    out: set[int] = set()
    for rows_in in groups.values():
        concluded = [row for row in rows_in if _concluded(row)]
        if not concluded:
            continue
        newest = max(concluded, key=lambda r: (_row_time(r), _row_id(r)))
        usable_time = bool(_row_time(newest))
        for row in concluded:
            if row is newest:
                continue
            if not usable_time and not _row_time(row) and _row_id(row) < 0:
                continue  # no ordering evidence at all: never call this superseded
            if (_row_time(row), _row_id(row)) < (_row_time(newest), _row_id(newest)):
                if _row_id(row) >= 0:
                    out.add(_row_id(row))  # id-less rows cannot be identified by the caller
    return out
