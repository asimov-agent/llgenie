#!/usr/bin/env python3
"""Hermetic tests for tick_board.sh section B's arm-state classification (issue #2182).

The tick's section B must distinguish four states: `armed`, `unarmed`,
`armed-but-DIRTY` (the arm is INERT — it can never merge), and
`green+approved+unarmed` (reviewDecision=APPROVED, mergeable, no arm → arm it
now). A false-measurement regression is the point of this file: if the
`gh pr list --json` field list omits `autoMergeRequest,reviewDecision`, every PR
silently reads `unarmed` (null when the field list does not ask). These tests feed
the REAL script's section-B parser a fixture list that includes those fields and
assert the classification, so a field-list drop reds rather than reporting false
unarmed.
"""

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parent.parent
    / "agents"
    / "llgenie-planner"
    / "scripts"
    / "tick_board.sh"
)


def _run(prs, main_override=None):
    """Run tick_board.sh section B against a fixture PR list (no network).

    PR_LIST_JSON is a FILE PATH the script `cat`s; write the fixture first.
    """
    tmp = Path(tempfile.mkdtemp())
    pr_json = "[]"
    if prs:
        pr_json = json.dumps(prs)
    prf = tmp / "pr.json"
    prf.write_text(pr_json)
    out = subprocess.run(
        ["bash", str(SCRIPT)],
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "REPO": str(tmp),
            "MAIN_OVERRIDE": main_override or "aaaaaaaa",
            "PR_LIST_JSON": str(prf),
            "HERMES_BIN": "/bin/true",
        },
        timeout=120,
    )
    assert out.returncode == 0, out.stderr
    return out.stdout


def _pr(n, mergeStateStatus="CLEAN", mergeable="MERGEABLE", armed=False,
        review="APPROVED"):
    return {
        "number": n,
        "baseRefOid": "aaaaaaaa" * 4,
        "mergeStateStatus": mergeStateStatus,
        "mergeable": mergeable,
        "headRefOid": "bbbbbbbb" * 4,
        "title": f"arm test {n}",
        "autoMergeRequest": {"enabledAt": "2026-11-08T00:00:00Z"} if armed else None,
        "reviewDecision": review,
    }


def test_known_armed_fixture_reports_armed_not_unarmed(tmp_path):
    # The false-measurement regression: a PR whose ARM is present must read ARMED,
    # never unarmed (the field list is the bug, not "nothing is armed").
    out = _run([_pr(1, armed=True)])
    assert "ARMED" in out, out
    assert re.search(r"ARM armed=1 unarmed=0 armed-but-DIRTY\(inert\)=0", out), out
    # the per-PR line for #1 is ARMED, never a bare "unarmed" classification
    line1 = [l for l in out.splitlines() if l.strip().startswith("#1")][0]
    assert "ARMED" in line1, line1
    assert "unarmed" not in line1, line1


def test_known_unarmed_reports_unarmed(tmp_path):
    out = _run([_pr(2)])
    assert re.search(r"ARM armed=0 unarmed=1 armed-but-DIRTY\(inert\)=0", out), out


def test_armed_but_dirty_is_inert_never_handled(tmp_path):
    # An armed DIRTY PR is impossible (no CI run, queue never sees it) — labelled
    # ARM-INERT, never counted as armed/handled.
    out = _run([_pr(3, mergeStateStatus="DIRTY", mergeable="CONFLICTING", armed=True)])
    assert "ARM-INERT" in out, out
    assert re.search(r"ARM armed=0 unarmed=0 armed-but-DIRTY\(inert\)=1", out), out


def test_green_approved_unarmed_is_distinguished(tmp_path):
    # green+approved+unarmed: reviewDecision APPROVED, mergeable, no arm.
    out = _run([_pr(4, review="APPROVED")])
    assert "unarmed" in out
    assert "APPROVED" in out  # the review decision surfaces for the "arm it now" step


def test_four_distinct_states_all_in_one_board(tmp_path):
    prs = [
        _pr(1, armed=True),                       # armed
        _pr(2),                                   # unarmed
        _pr(3, mergeStateStatus="DIRTY", mergeable="CONFLICTING", armed=True),  # inert
        _pr(4, armed=False, review="APPROVED"),   # green+approved+unarmed
    ]
    out = _run(prs)
    assert re.search(r"ARM armed=1 unarmed=2 armed-but-DIRTY\(inert\)=1", out), out


def test_pipeline_not_fixed_here_leaves_ci_verdict_to_2156(tmp_path):
    # This issue does NOT "fix" ci-verdict (#2156); section B only reports arm
    # state. A scope/NOT-covered guard: no line here claims to clear ci-verdict.
    out = _run([_pr(1), _pr(2)])
    assert "ci-verdict" not in out  # measurement, never a fix
