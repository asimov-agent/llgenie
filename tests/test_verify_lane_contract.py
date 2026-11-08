"""Hermetic tests for scripts/verify_lane_contract.py (issue #2260, AC: the
behavioural-contract check is not a rubber stamp).

The real script is run against scratch fixture profiles built in tmp_path via
`--root`, so no live ~/.hermes profile is touched. The points proven:

- a complete contract SOUL + materialised skill PASSES;
- an EMPTY SOUL FAILS (no contract at all);
- a SOUL that has every OTHER contract element but no `BOT … working on #`
  report line FAILS the report-line axis (the file-drift passes / content does
  not case from the issue);
- a SOUL that reports to nobody FAILS the communicate axis;
- a SOUL whose skills/ holds only .archive stubs FAILS skills-materialised;
- removing a lane's own-duty marker makes the checker red for that lane.
"""

import subprocess
import sys
from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parent.parent / "scripts" / "verify_lane_contract.py"
)

# A complete live-identical SOUL: every CONTRACT element + the lane's own duty.
GOOD_SOUL = """# llgenie-planner
BOT llgenie-planner · working on #100 · branch x · since 01:00Z · blocked on none · next y
Never merge, never push to main.
Bookend: start comment on the issue, finish comment with the head sha.
Behaviour changes land by issue+PR under agents/<profile>/, never a private edit.
I triage the board and dispatch every idle lane to its owning PR.
Report to the planner via message_agent and recall the failure class.
"""

LANE = "llgenie-planner"


def _write_scratch_profile(root, lane=LANE, soul=GOOD_SOUL, skills=True,
                           archived_only=False):
    """Build a scratch profile: SOUL.md (+ optional skills dir). Returns root."""
    prof = root / lane
    (prof / "SOUL.md").parent.mkdir(parents=True, exist_ok=True)
    (prof / "SOUL.md").write_text(soul)
    if skills:
        base = prof / "skills" / (".archive" if archived_only else "security")
        (base / "SKILL.md").parent.mkdir(parents=True, exist_ok=True)
        (base / "SKILL.md").write_text("# Duty skill\nDo security.\n")
    return root


def _run(root):
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root)],
        capture_output=True,
        text=True,
        env={**__import__("os").environ},
        timeout=60,
    )


def test_all_pass_with_complete_contract(tmp_path):
    _write_scratch_profile(tmp_path)
    r = _run(tmp_path)
    assert r.returncode == 0, r.stdout
    assert "1/1 lanes pass the behavioural contract" in r.stdout, r.stdout


def test_empty_soul_fails(tmp_path):
    _write_scratch_profile(tmp_path, soul="")
    r = _run(tmp_path)
    assert r.returncode == 1, r.stdout
    assert "FAIL" in r.stdout
    assert "report-line" in r.stdout


def test_missing_report_line_fails(tmp_path):
    # every OTHER element present, but no `BOT … working on #` line
    no_report = GOOD_SOUL.replace(
        "BOT llgenie-planner · working on #100 · branch x · since 01:00Z · blocked on none · next y\n",
        "",
    )
    _write_scratch_profile(tmp_path, soul=no_report)
    r = _run(tmp_path)
    assert r.returncode == 1, r.stdout
    assert "report-line" in r.stdout, r.stdout


def test_no_communication_fails(tmp_path):
    # a SOUL that reports to nobody must fail the communicate axis
    no_comm = GOOD_SOUL.replace(
        "Report to the planner via message_agent and recall the failure class.\n",
        "",
    )
    _write_scratch_profile(tmp_path, soul=no_comm)
    r = _run(tmp_path)
    assert r.returncode == 1, r.stdout
    assert "communicate" in r.stdout, r.stdout


def test_archived_only_skills_fail(tmp_path):
    _write_scratch_profile(tmp_path, skills=True, archived_only=True)
    r = _run(tmp_path)
    assert r.returncode == 1, r.stdout
    assert "skills-materialised" in r.stdout, r.stdout


def test_removing_own_duty_marker_reds(tmp_path):
    # remove the own-duty marker; nothing else changes. `llgenie-planner`'s duty
    # regex (triag|dispat|orchestrat|idle) never collides with its own name, so
    # removing the marker genuinely reds rather than matching the lane title.
    no_duty = GOOD_SOUL.replace(
        "I triage the board and dispatch every idle lane to its owning PR.\n", ""
    )
    _write_scratch_profile(tmp_path, soul=no_duty)
    r = _run(tmp_path)
    assert r.returncode == 1, r.stdout
    assert "own-duty" in r.stdout, r.stdout
