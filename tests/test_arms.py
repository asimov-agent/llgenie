from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import check_arms as am


def _run(args: list[str], monkeypatch) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(REPO / "scripts" / "check_arms.py"), *args],
                          capture_output=True, text=True, cwd=REPO)


def _fake_gh(tmp_path: Path, prs: list[dict]) -> Path:
    bindir = tmp_path / "bin"
    bindir.mkdir(parents=True, exist_ok=True)
    gh = bindir / "gh"
    gh.write_text(f'''#!{sys.executable}
import json, sys
if sys.argv[1:3] == ["pr", "list"]:
    print({json.dumps(prs)!r})
    sys.exit(0)
print(json.dumps(sys.argv[1:]), file=sys.stderr); sys.exit(1)
''')
    gh.chmod(0o755)
    return bindir


GREEN = [{"status": "COMPLETED", "conclusion": "SUCCESS"}]
IN_CI = [{"status": "COMPLETED", "conclusion": "SUCCESS"}, {"status": "IN_PROGRESS"}]
RED = [{"status": "COMPLETED", "conclusion": "SUCCESS"}, {"status": "COMPLETED", "conclusion": "FAILURE"}]


def _pr(number, *, base="main", draft=False, mergeable="MERGEABLE", auto=None,
        merge_state="BLOCKED", review="APPROVED", checks=None):
    """A board row as `gh pr list --json` renders it. Default: finished, green, approved, NOT queued —
    the stuck shape; queue tests pass merge_state/review/checks to move it out of that shape."""
    return {"number": number, "title": f"PR {number}", "isDraft": draft,
            "baseRefName": base, "mergeable": mergeable, "autoMergeRequest": auto,
            "mergeStateStatus": merge_state, "reviewDecision": review,
            "statusCheckRollup": GREEN if checks is None else checks}


def test_a_finished_mergeable_main_pr_that_is_unarmed_is_a_finding(tmp_path, monkeypatch):
    """Prevents (rule 16): a finished PR left on the board is invisible to every sweep."""
    bindir = _fake_gh(tmp_path, [_pr(1), _pr(2, auto={"mergeMethod": "SQUASH"})])
    monkeypatch.setenv("PATH", f"{bindir}:{os.environ['PATH']}")
    out = _run(["check"], monkeypatch)
    assert out.returncode == 1, out.stdout + out.stderr
    assert "1/2 armed, queued, or legitimately unfinished" in out.stdout, out.stdout


def test_a_draft_or_stacked_base_owes_no_arm(tmp_path, monkeypatch):
    """A draft (not finished) and a stacked base (cannot be armed, #964) must not be flagged."""
    bindir = _fake_gh(tmp_path, [_pr(1, base="feat/x"), _pr(2, draft=True)])
    monkeypatch.setenv("PATH", f"{bindir}:{os.environ['PATH']}")
    out = _run(["check"], monkeypatch)
    assert out.returncode == 0, out.stdout + out.stderr
    assert "2/2 armed, queued, or legitimately unfinished" in out.stdout, out.stdout


def test_a_conflicted_pr_is_not_finished_and_is_skipped(tmp_path, monkeypatch):
    """An unmergeable PR has nothing to arm into yet."""
    bindir = _fake_gh(tmp_path, [_pr(1, mergeable="DIRTY")])
    monkeypatch.setenv("PATH", f"{bindir}:{os.environ['PATH']}")
    out = _run(["check"], monkeypatch)
    assert out.returncode == 0, out.stdout + out.stderr
    assert "not mergeable: DIRTY" in out.stdout, out.stdout


# --- queue semantics (issue #2378): the gate reads the board the CI auto-merge lane reads ---


def test_a_mid_ci_pr_is_not_finished_and_is_not_a_finding(tmp_path, monkeypatch):
    """Negative control (#2378): on the PRE-FIX tree this row WAS a finding (the daily alarm was red on
    every healthy board because `mergeable == MERGEABLE` alone counted as finished). A PR whose check
    rollup still has IN_PROGRESS/QUEUED rows is work in progress, not a finding."""
    bindir = _fake_gh(tmp_path, [_pr(1, checks=IN_CI, review="REVIEW_REQUIRED"),
                                 _pr(2, checks=[], review="REVIEW_REQUIRED")])
    monkeypatch.setenv("PATH", f"{bindir}:{os.environ['PATH']}")
    out = _run(["check"], monkeypatch)
    assert out.returncode == 0, out.stdout + out.stderr
    assert "in CI (checks not terminal" in out.stdout, out.stdout


def test_a_clean_queued_pr_is_not_a_finding(tmp_path, monkeypatch):
    """The CI auto-merge job lands a green, CLEAN PR (AGENTS.md); CLEAN *is* the queue (#2378)."""
    bindir = _fake_gh(tmp_path, [_pr(1, merge_state="CLEAN")])
    monkeypatch.setenv("PATH", f"{bindir}:{os.environ['PATH']}")
    out = _run(["check"], monkeypatch)
    assert out.returncode == 0, out.stdout + out.stderr
    assert "queued (mergeStateStatus CLEAN" in out.stdout, out.stdout


def test_an_in_flight_review_chain_is_not_a_finding(tmp_path, monkeypatch):
    """A green-but-REVIEW_REQUIRED/CHANGES_REQUESTED PR has its verdict chain mid-flight — the lane
    still owns it; the alarm must not preempt the chain (#2378)."""
    bindir = _fake_gh(tmp_path, [_pr(1, review="REVIEW_REQUIRED"), _pr(2, review="CHANGES_REQUESTED")])
    monkeypatch.setenv("PATH", f"{bindir}:{os.environ['PATH']}")
    out = _run(["check"], monkeypatch)
    assert out.returncode == 0, out.stdout + out.stderr
    assert out.stdout.count("in-flight (review chain not landed") == 2, out.stdout


def test_a_green_approved_blocked_pr_without_an_arm_is_the_stuck_class(tmp_path, monkeypatch):
    """Rule 16 still bites: every check COMPLETED+SUCCESS, mergeable, review chain landed (APPROVED),
    yet neither armed nor CLEAN — nothing will land it. This is the class #2378 names."""
    bindir = _fake_gh(tmp_path, [_pr(1, merge_state="BLOCKED", review="APPROVED")])
    monkeypatch.setenv("PATH", f"{bindir}:{os.environ['PATH']}")
    out = _run(["check"], monkeypatch)
    assert out.returncode == 1, out.stdout + out.stderr
    assert "FINDING: green, review chain complete" in out.stdout, out.stdout


def test_a_green_behind_main_pr_is_a_finding_the_lane_must_rebase(tmp_path, monkeypatch):
    """The auto-merge job refuses BEHIND; a green, approved PR parked behind main owes a rebase (#2378)."""
    bindir = _fake_gh(tmp_path, [_pr(1, merge_state="BEHIND", review="APPROVED")])
    monkeypatch.setenv("PATH", f"{bindir}:{os.environ['PATH']}")
    out = _run(["check"], monkeypatch)
    assert out.returncode == 1, out.stdout + out.stderr
    assert "(mergeStateStatus BEHIND)" in out.stdout, out.stdout


def test_a_red_pr_is_work_in_progress_not_a_finished_finding(tmp_path, monkeypatch):
    """A PR whose checks ended RED is already named by CI; the arms alarm does not double-name it."""
    bindir = _fake_gh(tmp_path, [_pr(1, checks=RED, merge_state="BLOCKED")])
    monkeypatch.setenv("PATH", f"{bindir}:{os.environ['PATH']}")
    out = _run(["check"], monkeypatch)
    assert out.returncode == 0, out.stdout + out.stderr
    assert "red (CI already names this failure)" in out.stdout, out.stdout


def test_check_arms_lists_the_queue_fields_in_one_call():
    """The board audit stays one unfiltered list call (#1021) — and that call now carries the queue fields."""
    src = (REPO / "scripts" / "check_arms.py").read_text()
    assert "--json" in src
    assert "number,title,isDraft,baseRefName,mergeable,autoMergeRequest,mergeStateStatus,reviewDecision,statusCheckRollup" in src


def test_finished_unarmed_decision_branches_on_the_right_fields():
    assert am.finished_unarmed(_pr(1)) is True  # green, approved, BLOCKED, no arm -> finding
    assert am.finished_unarmed(_pr(1, auto={"mergeMethod": "SQUASH"})) is False
    assert am.finished_unarmed(_pr(1, draft=True)) is False
    assert am.finished_unarmed(_pr(1, base="feat/x")) is False
    assert am.finished_unarmed(_pr(1, mergeable="DIRTY")) is False
    assert am.finished_unarmed(_pr(1, checks=IN_CI, review="REVIEW_REQUIRED")) is False  # mid-CI (#2378)
    assert am.finished_unarmed(_pr(1, checks=[], review="REVIEW_REQUIRED")) is False  # no rows yet (#2378)
    assert am.finished_unarmed(_pr(1, merge_state="CLEAN")) is False  # queued by the CI job (#2378)
    assert am.finished_unarmed(_pr(1, review="REVIEW_REQUIRED")) is False  # verdict chain in flight
    assert am.finished_unarmed(_pr(1, checks=RED)) is False  # red CI, not finished work
    assert am.finished(_pr(1, checks=IN_CI)) is False  # mid-CI is not finished (#2378)
    assert am.finished(_pr(1)) is True  # green + mergeable + main-based + non-draft is finished
