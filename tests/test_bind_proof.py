#!/usr/bin/env python3
"""A proof run must bind to the PR head it is cited for (issue #1293).

The engine proof lane hands a reviewer a run id + verdict, but nothing bound the run's ``head_sha`` to the
PR's *current* head before the proof was accepted — a run that went green at ``abc1d3ac`` read as evidence
for a later push it never saw. These tests drive the REAL script (never a copy of its logic) against fixture
files shaped like the live path, and the acceptance is asymmetric: a superseded run must be caught (exit 1),
a run on the current head must pass (exit 0).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "bind_proof.py"


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)


def fixture(tmp_path: Path, pr_head: str, run_heads: dict[str, str]) -> Path:
    path = tmp_path / "fixture.json"
    path.write_text(json.dumps({"pr_head": pr_head, "run_heads": run_heads}), encoding="utf-8")
    return path


def test_a_run_on_the_current_head_passes(tmp_path):
    """The happy path: the proving run's head IS the PR's head — the proof counts, exit 0 names the sha."""
    f = fixture(tmp_path, "abc1d3ac", {"11111111": "abc1d3ac"})
    out = run("--pr", "9", "--run", "11111111", "--fixture", str(f))
    assert out.returncode == 0, out.stdout + out.stderr
    assert "abc1d3ac" in out.stdout


def test_a_run_at_an_older_head_fails(tmp_path):
    """The defect: a run that proved an older head must NOT count as current-head evidence (exit 1, 'superseded')."""
    f = fixture(tmp_path, "def0042", {"11111111": "abc1d3ac"})
    out = run("--pr", "9", "--run", "11111111", "--fixture", str(f))
    assert out.returncode == 1, out.stdout + out.stderr
    assert "superseded proof" in (out.stdout + out.stderr)
    assert "abc1d3ac" in (out.stdout + out.stderr)
    assert "def0042" in (out.stdout + out.stderr)


def test_several_runs_one_of_them_superseded_fails(tmp_path):
    """A proof is a set: ONE stale run voids the whole hand, even when the other runs are on the head."""
    f = fixture(tmp_path, "def0042", {"11111111": "def0042", "22222222": "abc1d3ac"})
    out = run("--pr", "9", "--run", "11111111", "--run", "22222222", "--fixture", str(f))
    assert out.returncode == 1, out.stdout + out.stderr
    assert "superseded proof" in (out.stdout + out.stderr)
    assert "22222222" in (out.stdout + out.stderr)


def test_a_missing_run_head_in_the_fixture_is_a_bad_invocation(tmp_path):
    """A run we cannot measure is exit 2 (bad invocation), never a clean pass — the gate must not accept proof it cannot check."""
    f = fixture(tmp_path, "def0042", {"11111111": "def0042"})
    out = run("--pr", "9", "--run", "11111111", "--run", "99999999", "--fixture", str(f))
    assert out.returncode == 2, out.stdout + out.stderr
    assert "lacks pr_head and every run head" in (out.stdout + out.stderr) or "99999999" in (out.stdout + out.stderr)


def test_pr_is_required():
    """Without a PR the invocation is malformed — a gate that runs with no target proves nothing."""
    out = run("--run", "11111111")
    assert out.returncode == 2, out.stdout
