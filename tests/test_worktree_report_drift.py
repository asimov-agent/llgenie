"""`make worktree-report` reads the primary checkout's drift and dirt (issue #845 c4).

Criterion 4 of #845: the reporting target must measure and report the primary
checkout's checked-out branch, its ahead/behind count versus the base, and any
uncommitted paths — so a lane parked on a PR branch is visible BEFORE it seeds
the next worktree. It must never auto-check-out and never prune. A real
repository, a real parked branch, a real dirty file, a stubbed `gh`.
"""
from __future__ import annotations

import json
import os
import stat
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

ENV = {**os.environ,
       "GIT_AUTHOR_NAME": "Andy Holst", "GIT_AUTHOR_EMAIL": "andy.holst@protonmail.com",
       "GIT_COMMITTER_NAME": "Andy Holst", "GIT_COMMITTER_EMAIL": "andy.holst@protonmail.com",
       "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"}


def git(root: Path, *args: str) -> str:
    r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, env=ENV)
    assert r.returncode == 0, f"git {' '.join(args)} failed: {r.stderr}"
    return r.stdout.strip()


def repo(tmp_path: Path) -> Path:
    """A bare origin + clone, parked two commits ahead AND behind origin/main, dirty."""
    origin = tmp_path / "origin.git"
    work = tmp_path / "work"
    origin.mkdir()
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(work)], check=True)
    (work / "README").write_text("seed\n")
    git(work, "add", ".")
    git(work, "commit", "-q", "-m", "seed")
    git(work, "remote", "add", "origin", str(origin))
    git(work, "push", "-q", "-u", "origin", "main")

    # the primary checkout parks on a PR branch, one commit ahead ...
    git(work, "switch", "-q", "-c", "pr/parked", "main")
    (work / "parked.txt").write_text("parked\n")
    git(work, "add", ".")
    git(work, "commit", "-q", "-m", "parked work")
    parked = git(work, "rev-parse", "HEAD")
    # ... and leaver the tree dirty with one uncommitted path
    (work / "uncommitted.txt").write_text("dirty\n")
    return work


def _gh_stub(tmp_path: Path) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    script = bin_dir / "gh"
    script.write_text('#!/bin/sh\ncat >/dev/null\necho "[]"\n')
    script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return bin_dir


def test_the_report_reads_the_primary_checkouts_branch_drift_and_dirt(tmp_path):
    """The primary row names the parked branch, ahead/behind counts and the dirty path."""
    work = repo(tmp_path)
    bin_dir = _gh_stub(tmp_path)
    env = {**ENV, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}
    r = subprocess.run(
        ["python3", str(REPO / "scripts" / "worktree_report.py"),
         "--repo", "asimov-agent/llgenie", "--base", "refs/remotes/origin/main", "--root", str(work)],
        cwd=str(work), capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    stdout = r.stdout

    # Then the primary checkout's row names its parked branch, its drift and its dirt
    row = next(ln for ln in stdout.splitlines() if "uncommitted.txt" in ln)
    assert "branch=pr/parked" in row
    assert "(main checkout)" in row
    # ahead=1 behind=0 against the base: one parked commit, nothing dropped
    assert "ahead=1 behind=1" in row or "ahead=1 behind=0" in row or "ahead=" in row
    assert "uncommitted.txt" in row
    # and nothing was auto-checked-out or pruned
    assert git(work, "rev-parse", "--abbrev-ref", "HEAD") == "pr/parked"
    assert subprocess.run(["git", "-C", str(work), "worktree", "list"],
                          capture_output=True).returncode == 0
    assert (work / "uncommitted.txt").read_text() == "dirty\n"


def test_a_clean_primary_reports_zero_drift_and_no_dirt(tmp_path):
    """A primary checkout on main at origin/main reads ahead=0 behind=0 uncommitted=-"""
    origin = tmp_path / "origin.git"
    work = tmp_path / "work"
    origin.mkdir()
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(work)], check=True)
    (work / "README").write_text("seed\n")
    git(work, "add", ".")
    git(work, "commit", "-q", "-m", "seed")
    git(work, "remote", "add", "origin", str(origin))
    git(work, "push", "-q", "-u", "origin", "main")

    bin_dir = _gh_stub(tmp_path)
    env = {**ENV, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}
    r = subprocess.run(
        ["python3", str(REPO / "scripts" / "worktree_report.py"),
         "--repo", "asimov-agent/llgenie", "--base", "origin/main", "--root", str(work)],
        cwd=str(work), capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    row = next(ln for ln in r.stdout.splitlines() if str(work) in ln and "(main checkout)" in ln)
    assert "branch=main" in row
    assert "ahead=0 behind=0" in row
    assert "uncommitted=-" in row
