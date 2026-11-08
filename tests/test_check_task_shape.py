"""Hermetic tests for scripts/check_task_shape.py (issue #2123).

The guard refuses a task shape that can never produce a PR: an implementation-class task
assigned to `llgenie-planner` (the orchestrator never implements), or a branch-producing task in a
`scratch` workspace (no checkout to edit). Both faults made t_fe3d094f unrunnable for 51 minutes.
The tests pin the two refusals (each naming the offending field), the owner table, and the NEGATIVE
CONTROL: a legitimately-assigned implementation task (`llgenie-issse-implementer` + `worktree`) is
still accepted.

These run the REAL pure `refuse()` function imported from the script, and the real `scan` CLI
against fixture board JSON — no mocks of the product, only fixture text and board shapes.
"""

import json
import subprocess
import sys
from pathlib import Path

from scripts import check_task_shape as g

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "check_task_shape.py"

#: An implementation-class title (the AC's canonical example: "open a branch and a PR").
IMPL_TITLE = "implement #2089 as a reviewable PR: open a branch and author the code"
DOCS_TITLE = "document the change: add the agent-wiki note and CHANGES.md row"
PIPE_TITLE = "wire the workflow: add the make target and the ci- pipeline gate"
REBASE_TITLE = "rebase the branch onto origin/main and resolve the merge conflict"


def test_assignee_refusal_names_field_and_owner():
    """An implementation task assigned to the orchestrator is refused, naming `assignee` and the
    lane that owns the class (AC-1/AC-5)."""
    reasons = g.refuse(g.PLANNER, "worktree", IMPL_TITLE)
    assert reasons, "expected a refusal for planner-assigned implementation work"
    assert any("assignee" in r for r in reasons)
    assert any(g.CLASS_OWNER["implementation"] in r for r in reasons)
    assert any("never implements" in r or "never-implement" in r for r in reasons)


def test_workspace_refusal_names_field_and_remedy():
    """A branch-producing task in a scratch workspace is refused, naming `workspace` and the
    worktree/dir remedy (AC-2)."""
    reasons = g.refuse("llgenie-issse-implementer", "scratch", IMPL_TITLE)
    assert reasons
    assert any("workspace" in r for r in reasons)
    assert any("worktree" in r for r in reasons)
    assert any("dir:<existing-worktree>" in r for r in reasons)


def test_negative_control_legit_implementation_task_accepted():
    """`llgenie-issse-implementer` + `worktree` + an implementation title -> NO refusal (AC-3)."""
    assert g.refuse(g.CLASS_OWNER["implementation"], "worktree", IMPL_TITLE) == []


def test_non_branch_task_scratch_is_acceptable():
    """A task with no work-class markers (research/report) is not refused for a scratch workspace:
    a read has no branch to build."""
    assert g.refuse("llgenie-issse-implementer", "scratch", "measure the failure and report") == []
    assert g.refuse(g.PLANNER, "scratch", "recall the prior diagnosis and report") == []


def test_specified_workspace_defaults_to_scratch():
    """An unspecified workspace value is treated as scratch (the creation default, AC-2)."""
    assert g.workspace_default(None) == "scratch"
    assert g.workspace_default("") == "scratch"
    assert g.workspace_default("scratch") == "scratch"
    assert g.workspace_default("worktree") == "worktree"


def test_owner_table_names_every_class_owner():
    """The refusal names the correct owner for each work class (AC-5, subset check): each required
    class has an owner, and no class is mapped to the planner."""
    required = {
        "implementation": "llgenie-issse-implementer",
        "docs": "llgenie-documentation-maintainer",
        "pipeline": "llgenie-ci-pipelines-maintainer",
        "rebase": "llgenie-pr-merge-conflict",
    }
    for cls, owner in required.items():
        assert cls in g.CLASS_OWNER, f"{cls} has no owning lane in the table"
        assert g.CLASS_OWNER[cls] == owner, f"{cls} owned by {g.CLASS_OWNER[cls]}, not {owner}"
        assert owner != g.PLANNER, f"{cls} must not be owned by the orchestrator"


def test_refuse_across_every_work_class():
    """Every branch-producing class is refused on the planner and on a scratch workspace, so no
    work class slips through as 'belongs to the planner'."""
    for cls, owner in g.CLASS_OWNER.items():
        title = {  # one title per class, distinct enough to match only that class
            "implementation": IMPL_TITLE,
            "docs": DOCS_TITLE,
            "pipeline": PIPE_TITLE,
            "rebase": REBASE_TITLE,
        }[cls]
        assert g.classify(title), f"title for {cls} did not classify as branch-producing"
        assert g.refuse(g.PLANNER, "worktree", title), f"planner not refused for {cls} work"
        assert g.refuse(owner, "scratch", title), f"scratch not refused for {cls} work"
        assert g.refuse(owner, "worktree", title) == [], f"legit {cls} task was refused"


def test_scan_surfaces_a_blocked_misassigned_task(tmp_path):
    """The orchestrator-pass-report leg surfaces a blocked task whose assignee cannot do its class
    (AC-4), and stays silent on a correctly-owned blocked task."""
    board = [
        {"id": "t_bad", "assignee": g.PLANNER, "status": "blocked",
         "workspace_kind": "scratch", "title": IMPL_TITLE},
        {"id": "t_good", "assignee": g.CLASS_OWNER["implementation"], "status": "blocked",
         "workspace_kind": "worktree", "title": IMPL_TITLE},
        {"id": "t_running", "assignee": g.CLASS_OWNER["implementation"], "status": "running",
         "workspace_kind": "worktree", "title": IMPL_TITLE},
    ]
    kj = tmp_path / "board.json"
    kj.write_text(json.dumps(board))
    r = subprocess.run([sys.executable, str(SCRIPT), "scan", "--kanban-json", str(kj)],
                       capture_output=True, text=True)
    assert r.returncode == 1, f"expected scan to find the misassignment: {r.stdout}"
    assert "MISASSIGNED t_bad" in r.stdout
    assert "t_good" not in r.stdout and "t_running" not in r.stdout


def test_scan_clean_board_exits_zero(tmp_path):
    kj = tmp_path / "board.json"
    kj.write_text(json.dumps([{"id": "t_ok", "assignee": g.CLASS_OWNER["docs"], "status": "blocked",
                               "workspace_kind": "worktree", "title": DOCS_TITLE}]))
    r = subprocess.run([sys.executable, str(SCRIPT), "scan", "--kanban-json", str(kj)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout
    assert "MISASSIGNED" not in r.stdout
