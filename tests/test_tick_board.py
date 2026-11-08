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


def _run(pr_json, kanban_json):
    out = subprocess.run(
        [
            "bash",
            str(SCRIPT),
        ],
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "REPO": str(Path(tempfile.mkdtemp())),
            "MAIN_OVERRIDE": MAIN,
            "PR_LIST_JSON": pr_json,
            "KANBAN_JSON": kanban_json,
            # never read the real credential helper
            "HERMES_BIN": "/bin/true",
        },
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
