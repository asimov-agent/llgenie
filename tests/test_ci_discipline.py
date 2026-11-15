"""Hermetic tests for the CI discipline gate (issue #2701).

Every failure direction is proven against a COPY of the real tree: the gate
must be green on this repository as it stands, and red (naming the offender)
when a fixture tree (a) schedules a lane outside the allow-list, (b) lets an
allow-listed lane lose its clock, (c) gives the tests-only pipeline an agent
job, (d) re-schedules a deactivated agent lane, or (e) loses the durable
AGENTS.md section. The gate is driven through its documented `check`/`report`
commands with `--root`, never by importing private helpers.
"""
from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "check_ci_discipline.py"
WORKFLOWS = REPO / ".github" / "workflows"
SCHEDULED_ALLOW_SAMPLE = "auto-merge.yml"


def _tree(tmp_path: pathlib.Path) -> pathlib.Path:
    """A copy of the tree carrying exactly the inputs the gate reads."""
    root = tmp_path / "tree"
    (root / ".github").mkdir(parents=True)
    shutil.copytree(WORKFLOWS, root / ".github" / "workflows")
    shutil.copy(REPO / "AGENTS.md", root / "AGENTS.md")
    return root


def _run(root: pathlib.Path, command: str = "check") -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), command, "--root", str(root)],
        capture_output=True, text=True,
    )


# ---------------------------------------------------------------- the real tree


def test_the_gate_is_green_on_this_repository():
    proc = _run(REPO)
    assert proc.returncode == 0, proc.stderr
    assert "check-ci-discipline: OK" in proc.stdout


def test_report_names_the_measured_surface_and_always_exits_zero(tmp_path):
    root = _tree(tmp_path)
    proc = _run(root, "report")
    assert proc.returncode == 0
    out = proc.stdout
    for lane in ("engine-bump.yml", "auto-merge.yml", "all-pipelines.yml"):
        assert lane in out, out
    # The deactivated lanes appear nowhere as scheduled allow-listed entries.
    assert "issue-bot.yml" not in out.split("\n  ")[1] if "\n  " in out else True
    assert "agent-leg/agent-image users:" in out


# ------------------------------------------------------- failure directions


def test_a_new_schedule_outside_the_allow_list_is_a_finding(tmp_path):
    root = _tree(tmp_path)
    new_lane = root / ".github" / "workflows" / "midnight-sweeper.yml"
    new_lane.write_text(
        "name: midnight-sweeper — a fixture lane that schedules itself into the tree\n"
        "on:\n"
        "  schedule:\n"
        "    - cron: \"5 0 * * *\"\n"
        "  workflow_dispatch:\n"
        "jobs:\n"
        "  sweep:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - run: echo sweep\n"
    )
    proc = _run(root)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "midnight-sweeper.yml" in proc.stderr
    assert "allow-list" in proc.stderr


def test_an_allow_listed_lane_losing_its_clock_is_a_stale_allow_list(tmp_path):
    root = _tree(tmp_path)
    target = root / ".github" / "workflows" / SCHEDULED_ALLOW_SAMPLE
    text = target.read_text()
    stripped = text.replace("  schedule:\n    - cron: \"3,33 * * * *\"\n", "", 1)
    assert stripped != text, "fixture could not remove the clock — auto-merge.yml shape changed"
    target.write_text(stripped)

    proc = _run(root)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert SCHEDULED_ALLOW_SAMPLE in proc.stderr
    assert "stale allow-list" in proc.stderr


def test_the_tests_only_pipeline_may_not_gain_an_agent_job(tmp_path):
    root = _tree(tmp_path)
    target = root / ".github" / "workflows" / "ci.yml"
    text = target.read_text()
    injected = text.replace(
        "steps:",
        "steps:\n      - name: smuggled agent leg\n        uses: ./.github/actions/agent-leg",
        1,
    )
    assert injected != text, "fixture could not inject the marker — ci.yml shape changed"
    target.write_text(injected)

    proc = _run(root)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "ci.yml" in proc.stderr
    assert "tests-only" in proc.stderr


def test_a_deactivated_agent_lane_may_not_schedule_itself_again(tmp_path):
    root = _tree(tmp_path)
    target = root / ".github" / "workflows" / "issue-bot.yml"
    text = target.read_text()
    rescheduled = text.replace(
        "  issues:\n    types: [labeled]",
        "  issues:\n    types: [labeled]\n  schedule:\n    - cron: \"23 6 * * *\"",
        1,
    )
    assert rescheduled != text, "fixture could not re-add the clock — issue-bot.yml shape changed"
    target.write_text(rescheduled)

    proc = _run(root)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "issue-bot.yml" in proc.stderr
    assert "dispatch-only" in proc.stderr


def test_the_durable_agents_md_section_is_pinned(tmp_path):
    root = _tree(tmp_path)
    agents = root / "AGENTS.md"
    text = agents.read_text()
    import scripts  # noqa: F401  (path only — the gate's own constants are read from the file it checks)

    from_gate = (REPO / "scripts" / "check_ci_discipline.py").read_text()
    header = [l for l in from_gate.splitlines() if l.startswith('AGENTS_SECTION_HEADER = "')][0].split('"')[1]
    assert header in text, "the real AGENTS.md must carry the section the gate pins"
    agents.write_text(text.replace(header, header.replace("CI pipeline discipline", "retired discipline")))

    proc = _run(root)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "AGENTS.md" in proc.stderr
    assert "CI-discipline section" in proc.stderr


def test_the_dispatch_roster_is_pinned_and_the_blanket_ban_is_not(tmp_path):
    """#2718: the gate pins the dispatch roster (owner/collaborator/GitHub), not
    the old blanket-ban sentence. Replacing the roster with the blanket ban is
    a finding; keeping the roster is green."""
    root = _tree(tmp_path)
    agents = root / "AGENTS.md"
    text = agents.read_text()
    roster = "owner, a collaborator, and GitHub itself"
    assert roster in text, "the real AGENTS.md must name the dispatch roster (#2718)"
    assert "gh run rerun" in text, "the queue-pumping ban must stay in the section"
    agents.write_text(text.replace(roster, "never manually starts a CI pipeline"))

    proc = _run(root)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "AGENTS.md" in proc.stderr


# --------------------------------------------------------------- wiring seams


def test_the_gate_is_a_make_target_and_report_sibling_exist():
    from conftest import makefiles_text

    text = makefiles_text(REPO)
    assert "check-ci-discipline:" in text
    assert "ci-discipline-report:" in text
    # ci-unit runs it: the gate sits in scripts/ci_unit.py's MAKE_SEQUENCE
    # (the ci-unit recipe's home since issue #2675/#2705), right after check-wiring.
    from scripts import ci_unit
    targets = ci_unit.sequence_targets()
    assert "check-ci-discipline" in targets
    assert targets[targets.index("check-ci-discipline") - 1] == "check-wiring"
    assert any(".PHONY" in line and "check-ci-discipline" in line for line in text.splitlines())  # declared .PHONY
    assert any(".PHONY" in line and "ci-discipline-report" in line for line in text.splitlines())


def test_the_gate_is_classified_by_the_issue_bot_gate_roster():
    sys.path.insert(0, str(REPO))
    from scripts.issue_bot_gates import DEFERRED, FAST_GATES

    assert "check-ci-discipline" in DEFERRED
    assert "check-ci-discipline" not in FAST_GATES
