#!/usr/bin/env python3
"""A hold has to name the issue that lifts it (issue #948).

The owner's ruling: `do-not-merge` means *a known defect with a tracked remedy* — never "this lane would rather
not". A PR a bot implemented cannot carry it by default, and a lane that places it must file the issue that makes
the tag removable and say so where a reader can see it.

Why a gate: `mergeStateStatus` reads `BLOCKED` for a hold with a remedy and for one without, so every existing
check treats the two identically — a hold with no exit condition is indistinguishable from abandonment, and it
outlives the lane that placed it.

These tests drive the REAL script against fixture files (the shape the live path builds), never a copy of its
logic. Each rejection is its own test, because the rule is a rejection: a passing mention of an issue is not a
remedy, and that is exactly what every held PR on this board was doing when the issue was filed.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "check_holds.py"


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)


def fixture(tmp_path: Path, prs: list[dict]) -> Path:
    path = tmp_path / "prs.json"
    path.write_text(json.dumps(prs), encoding="utf-8")
    return path


def test_a_hold_with_no_resolving_issue_fails(tmp_path):
    """The defect the issue was filed for: a tag with no exit condition is abandonment."""
    prs = fixture(tmp_path, [{
        "number": 904, "title": "held for no written reason", "body": "## Problem\nsomething",
        "comments": [{"body": "parking this until someone looks"}],
    }])
    out = run("check", "--fixture", str(prs))
    assert out.returncode == 1, out.stdout + out.stderr
    assert "#904" in out.stdout
    assert "no resolving issue" in out.stdout


def test_a_passing_mention_of_an_issue_is_not_a_remedy(tmp_path):
    """Measured on the real board: every held PR named issues in passing (blocked on #767, see #892)."""
    prs = fixture(tmp_path, [{
        "number": 788, "title": "mentions many issues", "body": "supersedes #786, see #892 and #894",
        "comments": [{"body": "this was blocked on #767 for a while"}],
    }])
    out = run("check", "--fixture", str(prs))
    assert out.returncode == 1, out.stdout
    assert "#788" in out.stdout


def test_a_hold_that_names_its_remedy_passes(tmp_path):
    """`resolves #NNN` in a comment is the condition under which the tag comes off."""
    prs = fixture(tmp_path, [{
        "number": 846, "title": "held with a remedy",
        "body": "",
        "comments": [{"body": "held until #948 lands: the cron collision is what blocks it"}],
    }])
    out = run("check", "--fixture", str(prs))
    assert out.returncode == 0, out.stdout
    assert "#948" in out.stdout
    assert "NO REMEDY" not in out.stdout


def test_a_markdown_heading_is_not_an_issue_reference(tmp_path):
    """`## Problem` must not be read as issue #0 or a number — the naive `#\\d+` regex reads headings as noise."""
    prs = fixture(tmp_path, [{
        "number": 786, "title": "headings everywhere", "body": "## Problem\n## Fix\nno issue named",
        "comments": [],
    }])
    out = run("check", "--fixture", str(prs))
    assert out.returncode == 1, out.stdout
    assert "NO REMEDY" in out.stdout


def test_report_mode_never_fails_so_it_can_be_read_on_a_bad_board(tmp_path):
    """A board with a bad hold must still be reportable — the auditor needs to read it more than anyone."""
    prs = fixture(tmp_path, [{"number": 1, "title": "held", "body": "", "comments": []}])
    out = run("report", "--fixture", str(prs))
    assert out.returncode == 0, out.stdout
    assert "#1" in out.stdout


def test_the_workflow_runs_the_gate_on_a_schedule_and_on_pull_requests():
    """A hold cannot outlive its remedy only if something looks on a timer, not just when a PR changes."""
    workflow = (REPO / ".github" / "workflows" / "holds.yml").read_text()
    assert "make check-holds" in workflow, "the workflow must call the gate"
    assert "schedule:" in workflow and "cron:" in workflow, "a hold that nobody touches needs a timer"
    assert "pull_request:" in workflow, "and a fresh hold must be caught when it is placed"
    assert "workflow_dispatch:" in workflow


def test_the_phrasings_the_board_actually_uses_are_recognised(tmp_path):
    """Regression from the first live run: #904 states its remedy as "resolving issue #949" and
    "lifting condition … the five criteria in #949", and a `resolves|blocked by`-only rule called it NO REMEDY.

    A false red on a properly documented hold is as expensive as a missed one: it teaches the lane to phrase
    around the gate instead of writing the remedy.
    """
    prs = fixture(tmp_path, [{
        "number": 904, "title": "held with a documented remedy",
        "body": "closes #824 and mentions #860 for context",
        "comments": [
            {"body": "State check: hold is in place. resolving issue #949, lifting condition unchanged: "
                     "the five criteria in #949."},
        ],
    }])
    out = run("check", "--fixture", str(prs))
    assert out.returncode == 0, out.stdout
    assert "#949" in out.stdout
