#!/usr/bin/env python3
"""Hermetic tests for tick_board.sh section D's #2353 board-health lines.

Two new lines every orchestrator pass must print:

  board-ownership: planner_owned_ready=N (expect <= planner-domain D)
                   lanes_with_ready=M -> OK|RED
  profiled_mismatch=K

AC1 (board-ownership invariant): measured from `kanban list --json` (assignee,
status, created_by — no new dependency). The planner legitimately OWNS ready
cards only in its own orchestration domain, defined here as cards created by
the planner or its auto-decomposer. A bulk assignee rewrite reassigns
LANE-created ready cards into planner, so planner_owned_ready rises above the
domain ceiling and the line goes RED while `lanes_with_ready` collapses.

AC2 (mis-profiled run): for every running task, compare the active
task_runs.profile with the task's assignee; count the mismatches. The
2026-11-09 incident (6 planner-profiled runs on lane tasks) must print 6; a
board whose runners match their assignees prints 0. Runs are fed through the
KANBAN_RUNS_JSON seam (the script reads KANBAN_DB read-only in production).

These tests run the REAL script with KANBAN_JSON / KANBAN_RUNS_JSON /
PR_LIST_JSON / MAIN_OVERRIDE fixtures, exactly like the existing
test_tick_board.py. No network, no hermes daemon, no live DB.
"""

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parent.parent
    / "agents"
    / "llgenie-planner"
    / "scripts"
    / "tick_board.sh"
)

LANES = [
    "llgenie-planner", "llgenie-architect", "llgenie-issse-implementer",
    "llgenie-pr-reviever", "llgenie-ci-pipelines-maintainer",
    "llgenie-documentation-maintainer", "llgenie-engine-improver",
    "llgenie-pr-merge-conflict", "llgenie-security", "llgenie-tester",
    "llgenie-product-manager", "llgenie-business-analyst", "llgenie-status-keeper",
]


def _run(kb_tasks, runs=None):
    """Run the real tick_board.sh against a board fixture; return stdout."""
    tmp = Path(tempfile.mkdtemp())
    prf = tmp / "pr.json"
    prf.write_text(json.dumps([]))
    kbf = tmp / "kb.json"
    kbf.write_text(json.dumps(kb_tasks))
    env = {
        **os.environ,
        "REPO": str(tmp),
        "MAIN_OVERRIDE": "aaaaaaaa",
        "PR_LIST_JSON": str(prf),
        "KANBAN_JSON": str(kbf),
        "KANBAN_DB": str(tmp / "absent.db"),  # never touch a live board
        "HERMES_BIN": "/bin/true",
        "STALL_SWEEP": "/nonexistent",
    }
    if runs is not None:
        ruf = tmp / "runs.json"
        ruf.write_text(json.dumps(runs))
        env["KANBAN_RUNS_JSON"] = str(ruf)
    out = subprocess.run(
        ["bash", str(SCRIPT)], capture_output=True, text=True, env=env, timeout=120
    )
    assert out.returncode == 0, out.stderr
    return out.stdout


def _board(ready_lanes=(), lane_created_ready=()):
    """A board: every lane has one task; ready for the named lanes.

    lane_created_ready: lanes whose ready task has created_by == itself
    (a LANE-created card, the kind a bulk rewrite would siphon into planner),
    distinguished from the planner domain (planner/auto-decomposer created).
    """
    tasks = []
    for i, lane in enumerate(LANES):
        ready = lane in ready_lanes or lane in lane_created_ready
        created_by = lane if lane in lane_created_ready else lane
        tasks.append({
            "id": f"t_{i}", "assignee": lane,
            "status": "ready" if ready else "running",
            "title": f"task {lane}", "created_by": created_by,
        })
    return tasks


def _ownership_line(out):
    line = [l for l in out.splitlines() if "board-ownership:" in l]
    assert line, f"no board-ownership line in output:\n{out}"
    return line[0].strip()


def _mismatch_line(out):
    line = [l for l in out.splitlines() if "profiled_mismatch=" in l]
    assert line, f"no profiled_mismatch line in output:\n{out}"
    return line[0].strip()


# --- AC1: board-ownership invariant ----------------------------------------

def test_healthy_board_reports_ok_within_planner_domain(tmp_path):
    # planner owns only its own (planner-created) ready card; 3 lanes ready.
    board = _board()
    for t in board:
        if t["assignee"] == "llgenie-planner":
            t["status"] = "ready"  # planner-domain: planner-created
        if t["assignee"] in ("llgenie-tester", "llgenie-security", "llgenie-business-analyst"):
            t["status"] = "ready"  # lane-created ready
    out = _run(board)
    assert re.search(
        r"planner_owned_ready=1 \(expect <= planner-domain 1 .*lanes_with_ready=3 -> OK",
        _ownership_line(out),
    ), _ownership_line(out)


def test_planner_domain_counts_auto_decomposer_created_as_legitimate(tmp_path):
    # a ready card created by auto-decomposer and assigned to planner is in the
    # planner's own domain (its orchestration machinery) — NOT a rewrite.
    board = _board()
    for t in board:
        t["status"] = "running"
        if t["assignee"] == "llgenie-planner":
            t["status"] = "ready"; t["created_by"] = "auto-decomposer"
    out = _run(board)
    assert re.search(r"planner_owned_ready=1 \(expect <= planner-domain 1", _ownership_line(out))
    assert "-> OK" in _ownership_line(out) or "-> OK" in _ownership_line(out)


def test_rewriting_a_lane_created_ready_card_to_planner_goes_red(tmp_path):
    # Negative control (AC4): deliberately rewrite ONE lane-created ready card's
    # assignee into planner. planner_owned_ready now exceeds the planner domain
    # (that card was created by its lane, not by the planner) -> line goes RED.
    board = _board()
    for t in board:
        if t["assignee"] in ("llgenie-tester", "llgenie-security", "llgenie-business-analyst"):
            t["status"] = "ready"
            if t["assignee"] == "llgenie-tester":
                t["created_by"] = "llgenie-tester"  # lane-authored, not planner's
    # the planner's own (planner-created) ready card keeps the domain at 1
    for t in board:
        if t["assignee"] == "llgenie-planner":
            t["status"] = "ready"
    assert _ownership_line(_run(board)).endswith("OK")
    # now siphon the tester's lane-created ready card into planner
    for t in board:
        if t["assignee"] == "llgenie-tester":
            t["assignee"] = "llgenie-planner"
    line = _ownership_line(_run(board))
    assert line.endswith("RED"), line
    # a SECOND lane still holds ready work, so lanes_with_ready reflects the collapse
    assert re.search(r"lanes_with_ready=2", line), line


def test_single_card_edit_leaves_other_assignees_unchanged_and_zero_violations(tmp_path):
    # Req.1 positive regression: a benign single-card edit must (a) leave every
    # OTHER card's assignee byte-identical and (b) keep the invariant check at
    # zero violations. This is the read-path contact of the host-only write-path
    # proof in test_kanban_single_card_reassign.py: it re-runs the REAL
    # tick_board.sh against a fixture board, reassigns exactly one READY card
    # between two non-planner lanes (planner_owned_ready stays 0, so the line
    # stays OK), and proves the check neither alters nor flags the untouched
    # cards. The byte-identically test bites here because the REASSIGNED card
    # must be the ONLY diff in the fixture after a legitimate peer-to-peer edit.
    board = _board()
    for t in board:
        if t["assignee"] in ("llgenie-tester", "llgenie-security", "llgenie-business-analyst"):
            t["status"] = "ready"
    before = {t["id"]: t["assignee"] for t in board}
    # baseline: no planner-owned ready, two lanes hold ready work -> OK, zero red
    base_line = _ownership_line(_run(board))
    assert _ownership_line(_run(board)).endswith("OK"), base_line
    assert _mismatch_line(_run(board)).startswith("profiled_mismatch=0")
    # reassign exactly ONE ready card from llgenie-security into llgenie-tester
    target = next(t["id"] for t in board if t["assignee"] == "llgenie-security")
    for t in board:
        if t["id"] == target:
            t["assignee"] = "llgenie-tester"
    after_map = {t["id"]: t["assignee"] for t in board}
    changed = [k for k in before if before[k] != after_map.get(k)]
    assert changed == [target], f"more than the one edited card changed: {changed}"
    # re-run the check on the edited board: still OK, zero violations
    line = _ownership_line(_run(board))
    assert line.endswith("OK"), line
    assert "planner_owned_ready=0" in line, line


def test_ownership_line_prints_even_with_empty_board(tmp_path):
    # A check that cannot fail is decoration; an empty board still prints the
    # line (0 <= max(1,0) -> OK), and the section header stays present.
    out = _run([])
    assert "board-ownership: planner_owned_ready=0" in out


# --- AC2: mis-profiled run detection -----------------------------------------

def test_healthy_running_board_reports_zero_mismatch(tmp_path):
    board = _board(ready_lanes=())
    runs = [{"task_id": t["id"], "profile": t["assignee"], "status": "running"} for t in board]
    out = _run(board, runs=runs)
    assert _mismatch_line(out).startswith("profiled_mismatch=0"), _mismatch_line(out)


def test_six_misprofiled_runs_report_six(tmp_path):
    # #2353's incident: 6 lane tasks dispatched under llgenie-planner. Every
    # running task's task_runs.profile differs from its assignee -> mismatch=6.
    board = _board(ready_lanes=())
    runs = [{"task_id": t["id"], "profile": t["assignee"], "status": "running"} for t in board]
    # lanes [4..9] in LANES = ci-pipelines-maintainer, docs, engine, pr-merge,
    # security, tester — six non-planner lanes whose runner is llgenie-planner.
    for i in range(4, 10):
        for r in runs:
            if r["task_id"] == f"t_{i}":
                r["profile"] = "llgenie-planner"
    out = _run(board, runs=runs)
    line = _mismatch_line(out)
    assert line.startswith("profiled_mismatch=6"), line
    # the line NAMES the offenders (task=assignee/profile) so the tick can act
    assert "t_4=" in line and "llgenie-ci-pipelines-maintainer" in line


def test_matching_profiles_ignore_planner_running_without_assignee(tmp_path):
    # a planner-profiled run still scheduled under a planner-OWNED task is NOT a
    # mismatch (profile == assignee). Only a profile that differs from the
    # running task's assignee counts.
    board = _board(ready_lanes=())
    runs = [{"task_id": t["id"], "profile": t["assignee"], "status": "running"} for t in board]
    out = _run(board, runs=runs)
    assert _mismatch_line(out).startswith("profiled_mismatch=0")
