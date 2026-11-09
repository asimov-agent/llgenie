"""The engine-build-pr-trigger concurrency group is scoped per PR head SHA (issue #1831).

Issue #1633 made a pin-bump PR dispatch the engine-build producer. But the trigger's
concurrency group was keyed only by PR number, so a `synchronize` push onto the same PR
(a rebase) queued behind the OLD head's build for up to ~90 minutes with zero jobs and a
frozen `updated_at` — the exact #1831 failure, and the reason a rebased PR reports a stale
guard while its new-head build never starts.

Issue #1831 resets the scope to the head SHA: `dangerouslyPush` on the same PR fires a NEW
trigger run for the new head instead of joining the old head's queue. This file pins that
contract *to the live workflow* (issue #301 scope-is-derived: whatever the workflow file
really says is the rule, so a hand-kept copy of the string in this test can never drift
away from the YAML it claims to describe):

- the `concurrency.group` carries BOTH the PR number and the PR head SHA
- `cancel-in-progress` stays `false`, so a stale-head trigger never cancels a producer
  run that is mid-build (#1102, #917)
- the trigger stays off `push` to main (#614), so a merge publishes on its own schedule
  rather than double-dispatching a full sweep. Issue #2381 adds `workflow_dispatch` (a
  manual re-drive with REQUIRED `base_ref` + `branch` inputs) beside `pull_request`,
  so the trigger surface is exactly `{pull_request, workflow_dispatch}`.

Unticked AC1/AC2 on #1831 are provable here, pre-merge, by this test — the head-SHA scope
is static text in the workflow, so whether a real rebase's run reports a guard job
immediately becomes a property of the YAML, not of a future live flight (reviewer
re-write-back path, issue #1644).
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
WF = REPO / ".github" / "workflows"
TRIGGER = WF / "engine-build-pr-trigger.yml"


def _load() -> dict:
    return yaml.safe_load(TRIGGER.read_text())


def _on(wf: dict) -> dict:
    """The workflow's `on:` block. YAML 1.1 reads the bare key `on` as the boolean True,
    so accept both spellings rather than depending on the loader (same convention as
    tests/test_bot_pipeline_isolation.py)."""
    on = wf.get("on") or wf.get(True)
    return on if isinstance(on, dict) else {}


def test_trigger_concurrency_group_carries_pr_head_sha():
    """The concurrency group is scoped per PR head, not just per PR number (#1831)."""
    wf = _load()
    group = wf["concurrency"]["group"]
    # group must interpolate the PR number and the PR head SHA — the #1831 fix
    assert "pull_request.number" in group
    assert "pull_request.head.sha" in group
    # and it must be the head-SHA scoped group, not the old PR-number-only form
    assert wf["concurrency"]["cancel-in-progress"] is False


def test_trigger_separate_group_per_head_not_shared_by_number():
    """Two different head SHAs on the same PR never share a group (the #1831 contract).

    The old group (`engine-build-pr-trigger-<number>`) joined a new head's run behind the
    old head's build; the fixed group keys on the head SHA so a synchronize/rebase starts
    a fresh run immediately instead of queueing (issue #1831)."""
    wf = _load()
    group_tpl = wf["concurrency"]["group"]
    assert group_tpl.startswith("engine-build-pr-trigger-")
    # the interpolated group differs solely by head sha for a fixed PR number
    g1 = group_tpl.replace("${{ github.event.pull_request.head.sha }}", "AAAA").replace("${{ github.event.pull_request.number }}", "42")
    g2 = group_tpl.replace("${{ github.event.pull_request.head.sha }}", "BBBB").replace("${{ github.event.pull_request.number }}", "42")
    assert g1 != g2


def test_trigger_not_cancelled_and_trigger_surface():
    """cancel-in-progress stays false (never cancel a live producer run, #917/#1102); the
    trigger surface is `pull_request` + `workflow_dispatch` (issue #2381) and never `push`
    to main (#614); and a manual dispatch is always scoped by its REQUIRED inputs."""
    wf = _load()
    assert wf["concurrency"]["cancel-in-progress"] is False
    on = _on(wf)
    assert set(on.keys()) == {"pull_request", "workflow_dispatch"}
    # the dispatch is scoped: both inputs are required so a re-drive always names its refs
    dispatch = on["workflow_dispatch"]
    if isinstance(dispatch, dict):
        inputs = (dispatch.get("inputs") or {})
        for key in ("base_ref", "branch"):
            assert key in inputs, f"dispatch input {key} missing"
            assert (inputs[key].get("required") is True), f"dispatch input {key} must be required"
    # and must react to a synchronize push (a rebase), which is the #1831 vehicle
    pr = on["pull_request"]
    if isinstance(pr, dict):
        types = pr.get("types", []) or []
        assert "synchronize" in types
        assert "opened" in types
        assert "reopened" in types
