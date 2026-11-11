"""Hermetic tests for agents/llgenie-planner/scripts/tick_board.sh (issue #2159).

The AC "a dry run against the 2026-11-08 state reproduces stale=12, dirty=2,
idle_non_planner=7" must be repeatable, not a one-off sighting. These tests run
the real script with PR_LIST_JSON / KANBAN_JSON / MAIN_OVERRIDE fixtures and
assert the exact totals the issue recorded, plus section-order and header
presence. No network, no gh, no hermes daemon — the fixtures stand in for the
CLIs, which is the repository's allowance for an external-command seam.

Env the script reads (all $HOME-relative): PR_LIST_JSON, KANBAN_JSON,
MAIN_OVERRIDE. REPO is pinned to a throwaway dir so section A never touches the
real checkout.
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

#: The 2026-11-08 state, as recorded in the issue (#2159 "Technical"): main was
#: 78c39175; 12 of 14 PRs sat on stale bases (4664bda7/520db900/e51f2fd0); 2 were
#: DIRTY; 7 non-planner lanes were idle.
STALE_BASES = ["4664bda7", "520db900", "e51f2fd0"]
MAIN = "78c39175"
N = 14
IDLE = {
    "llgenie-architect",
    "llgenie-issse-implementer",
    "llgenie-documentation-maintainer",
    "llgenie-tester",
    "llgenie-product-manager",
    "llgenie-business-analyst",
    "llgenie-status-keeper",
}
LANES = [
    "llgenie-planner",
    "llgenie-architect",
    "llgenie-issse-implementer",
    "llgenie-pr-reviever",
    "llgenie-ci-pipelines-maintainer",
    "llgenie-documentation-maintainer",
    "llgenie-engine-improver",
    "llgenie-pr-merge-conflict",
    "llgenie-security",
    "llgenie-tester",
    "llgenie-product-manager",
    "llgenie-business-analyst",
    "llgenie-status-keeper",
]


def _pr_fixture():
    prs = []
    for i in range(N):
        dirty = i in (2, 7)  # 2 of the 14 were DIRTY (issue: dirty=2)
        prs.append(
            {
                "number": 2000 + i,
                "baseRefOid": STALE_BASES[i % 3] if i < 12 else MAIN,
                "mergeStateStatus": "DIRTY" if dirty else "BLOCKED",
                "mergeable": "MERGEABLE",
                "headRefOid": f"abc{i}def",
                "title": f"test PR {2000 + i}",
            }
        )
    return prs


def _kanban_fixture():
    tasks = []
    for i, lane in enumerate(LANES):
        tasks.append(
            {
                "id": f"t_{i}",
                "assignee": lane,
                "status": "running" if lane not in IDLE else "ready",
                "title": f"task for {lane}",
            }
        )
    return tasks


def _run(pr_json, kanban_json, extra_env=None):
    env = {
        **os.environ,
        "REPO": str(Path(tempfile.mkdtemp())),
        "MAIN_OVERRIDE": MAIN,
        "PR_LIST_JSON": pr_json,
        "KANBAN_JSON": kanban_json,
        # hermetic: section D's mis-profiled-run check reads KANBAN_DB unless
        # KANBAN_RUNS_JSON is set; a missing path yields '[]' (mismatch 0).
        "KANBAN_DB": str(Path(tempfile.mkdtemp()) / "absent.db"),
        # never read the real credential helper
        "HERMES_BIN": "/bin/true",
    }
    if extra_env:
        env.update(extra_env)
    out = subprocess.run(
        [
            "bash",
            str(SCRIPT),
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    assert out.returncode == 0, out.stderr
    return out.stdout


def test_reproduces_2026_11_08_from_sections_b_and_c(tmp_path):
    pj = tmp_path / "pr.json"
    kj = tmp_path / "kb.json"
    pj.write_text(json.dumps(_pr_fixture()))
    kj.write_text(json.dumps(_kanban_fixture()))
    out = _run(str(pj), str(kj))
    assert re.search(r"TOTAL open=14\s+stale=12\s+dirty=2", out), out
    assert re.search(r"idle_non_planner=7", out), out


def test_sections_appear_in_fixed_order_a_through_g(tmp_path):
    pj = tmp_path / "pr.json"
    kj = tmp_path / "kb.json"
    pj.write_text(json.dumps([]))
    kj.write_text(json.dumps([]))
    out = _run(str(pj), str(kj))
    order = re.findall(r"===== ([A-G]\.) ", out)
    assert order == ["A.", "B.", "C.", "D.", "E.", "F.", "G."], order


def test_section_a_prints_sha_and_agents_size(tmp_path):
    pj = tmp_path / "pr.json"
    kj = tmp_path / "kb.json"
    pj.write_text(json.dumps([]))
    kj.write_text(json.dumps([]))
    out = _run(str(pj), str(kj))
    assert "main_sha: 78c39175" in out
    assert "fetched_at_utc:" in out
    # AGENTS size may be unreadable on the throwaway REPO; that is fine — the
    # header present with the sha is what a step quotes as evidence.
    assert "agents_md:" in out


#: issue #2450: `git rev-parse --short` reads THIS repo's main at 9 chars, while
#: gh's baseRefOid is the full 40-char sha. The old `[:8] != main` read every
#: current-main PR as STALE (measured at main 23faf9550: #2448 #2438 #2365 #2363
#: all base-CLEAN, all printed STALE).
LONG_MAIN = "23faf9550"
FULL_BASE_TIP = "23faf9550" + "0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5"  # 40 chars, same commit
FULL_BASE_OLD = "4664bda70" + "c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6"  # 40 chars, older commit


def _pr_base(n, base_oid):
    return {
        "number": n,
        "baseRefOid": base_oid,
        "mergeStateStatus": "CLEAN",
        "mergeable": "MERGEABLE",
        "headRefOid": "bbbbbbbb" * 5,
        "title": f"truncation test {n}",
    }


def test_full_length_base_at_a_long_main_is_fresh(tmp_path):
    """The #2450 regression: a 9-char main must match a 40-char base of the same commit."""
    pj = tmp_path / "pr.json"
    kj = tmp_path / "kb.json"
    pj.write_text(json.dumps([_pr_base(2448, FULL_BASE_TIP), _pr_base(2438, LONG_MAIN)]))
    kj.write_text(json.dumps([]))
    out = _run(str(pj), str(kj), {"MAIN_OVERRIDE": LONG_MAIN})
    assert re.search(r"TOTAL open=2\s+stale=0\s+dirty=0", out), out
    assert "STALE" not in out, out
    line = [l for l in out.splitlines() if l.strip().startswith("#2448")][0]
    assert "fresh" in line and "base=23faf955" in line, line


def test_genuinely_stale_base_is_stale_with_its_true_base(tmp_path):
    """AC3: a stale base at a 9-char main still reads STALE and prints its true base."""
    pj = tmp_path / "pr.json"
    kj = tmp_path / "kb.json"
    pj.write_text(json.dumps([_pr_base(2365, FULL_BASE_OLD)]))
    kj.write_text(json.dumps([]))
    out = _run(str(pj), str(kj), {"MAIN_OVERRIDE": LONG_MAIN})
    assert re.search(r"TOTAL open=1\s+stale=1\s+dirty=0", out), out
    line = [l for l in out.splitlines() if l.strip().startswith("#2365")][0]
    assert "STALE" in line and "base=4664bda7" in line, line


def test_tip_tag_is_length_robust(tmp_path):
    """Section F: a 40-char headSha at the 9-char main tip must tag TIP, not other."""
    pj = tmp_path / "pr.json"
    kj = tmp_path / "kb.json"
    rj = tmp_path / "runs.json"
    pj.write_text(json.dumps([]))
    kj.write_text(json.dumps([]))
    rj.write_text(json.dumps([
        {"databaseId": 1, "workflowName": "CI", "conclusion": "success",
         "status": "completed", "headSha": FULL_BASE_TIP},
        {"databaseId": 2, "workflowName": "CI", "conclusion": "failure",
         "status": "completed", "headSha": FULL_BASE_OLD},
    ]))
    out = _run(str(pj), str(kj), {"MAIN_OVERRIDE": LONG_MAIN, "RUN_LIST_JSON": str(rj)})
    tip_line = [l for l in out.splitlines() if "run=1" in l][0]
    other_line = [l for l in out.splitlines() if "run=2" in l][0]
    assert " TIP " in tip_line, tip_line
    assert "other" in other_line and "TIP" not in other_line, other_line
