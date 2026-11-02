"""A PR must be cut from origin/main itself — the foreign-commit gate (issue #845).

Critera 3 and 5 of #845: the gate fails a PR whose merge-base with
`refs/remotes/origin/main` is not `refs/remotes/origin/main` itself (the branch
carries commits from another PR — the #794 case), naming the foreign commit; and
it stays GREEN for a clean branch that is exactly one commit ahead of
`origin/main` (the negative control). Real commits, real merge-bases.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import check_pr_base as cpb  # noqa: E402

ENV = {**os.environ,
       "GIT_AUTHOR_NAME": "Andy Holst", "GIT_AUTHOR_EMAIL": "andy.holst@protonmail.com",
       "GIT_COMMITTER_NAME": "Andy Holst", "GIT_COMMITTER_EMAIL": "andy.holst@protonmail.com",
       "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"}


def git(root: Path, *args: str) -> str:
    r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, env=ENV)
    assert r.returncode == 0, f"git {' '.join(args)} failed: {r.stderr}"
    return r.stdout.strip()


def repo(tmp_path: Path) -> Path:
    """A bare origin and a clone on main, with refs/remotes/origin/main present."""
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
    git(work, "remote", "set-head", "origin", "main")
    return work


def test_a_foreign_commit_fails_and_is_named(tmp_path):
    """A branch cut from another PR (diverged from current origin/main) fails,#845.

    The #794 shape: the other PR branch was cut from an OLDER main and carries
    commits origin/main never saw; our branch cut from ITS tip (as a worktree
    inheriting the primary checkout's parked branch would) therefore has
    merge-base with CURRENT origin/main != origin/main. The foreign commit is
    named.
    """
    work = repo(tmp_path)

    # another PR branch: cut from the THEN-current main, work NOT pushed to main
    git(work, "switch", "-q", "-c", "pr/other", "main")
    (work / "other.txt").write_text("other lane\n")
    git(work, "add", ".")
    git(work, "commit", "-q", "-m", "other PR's work")
    foreign = git(work, "rev-parse", "HEAD")

    # origin/main ADVANCES past the point pr/other was cut at (a merge, another PR)
    git(work, "switch", "-q", "main")
    (work / "main2.txt").write_text("main moved on\n")
    git(work, "add", ".")
    git(work, "commit", "-q", "-m", "origin/main advances")
    git(work, "push", "-q", "origin", "main")

    # OUR branch cut from that stale other-PR tip — the #794 worktree shape
    git(work, "switch", "-q", "-c", "pr/mine", "pr/other")
    (work / "mine.txt").write_text("my lane\n")
    git(work, "add", ".")
    git(work, "commit", "-q", "-m", "my work")

    ok, foreign_commits = cpb.check(work, cpb.DEFAULT_BASE, "pr/mine")
    assert ok is False
    assert foreign_commits, "a foreign merge-base must name foreign commits"
    joined = " ".join(foreign_commits)
    assert foreign[:7] in joined or "other PR's work" in joined
    # and origin/main is genuinely not an ancestor of the head
    assert git(work, "rev-parse", "refs/remotes/origin/main") != git(work, "merge-base",
                                                                     "refs/remotes/origin/main", "pr/mine")


def test_a_clean_one_ahead_branch_passes(tmp_path):
    """The negative control: exactly one commit ahead of origin/main, no foreign work."""
    work = repo(tmp_path)
    git(work, "switch", "-q", "-c", "pr/clean", "main")
    (work / "clean.txt").write_text("one ahead\n")
    git(work, "add", ".")
    git(work, "commit", "-q", "-m", "one commit ahead, clean")
    ok, foreign = cpb.check(work, cpb.DEFAULT_BASE, "pr/clean")
    assert ok is True, foreign
    assert foreign == []


def test_a_missing_base_ref_is_a_failure_not_a_pass(tmp_path):
    """No refs/remotes/origin/main cannot read 'clean' — the gate must not fabricate one."""
    work = repo(tmp_path)
    git(work, "update-ref", "-d", "refs/remotes/origin/main")
    ok, foreign = cpb.check(work, cpb.DEFAULT_BASE, "main")
    assert ok is False
    assert foreign and "does not resolve" in foreign[0]


def test_the_cli_exits_correctly_for_both_cases(tmp_path):
    """`check` exits 0 for a clean one-ahead branch, 1 when a foreign commit is present."""
    work = repo(tmp_path)
    git(work, "switch", "-q", "-c", "pr/clean", "main")
    (work / "clean.txt").write_text("one ahead\n")
    git(work, "add", ".")
    git(work, "commit", "-q", "-m", "clean ahead")
    r = subprocess.run(["python3", str(REPO / "scripts" / "check_pr_base.py"), "check",
                        "--base", cpb.DEFAULT_BASE, "--rev", "pr/clean", "--cwd", str(work)],
                       capture_output=True, text=True, env=ENV)
    assert r.returncode == 0, r.stderr + r.stdout

    # origin/main advances; a branch cut from the OLD clean tip then carries foreign work
    git(work, "switch", "-q", "main")
    (work / "mainx.txt").write_text("main advances\n")
    git(work, "add", ".")
    git(work, "commit", "-q", "-m", "origin/main advances")
    git(work, "push", "-q", "origin", "main")

    git(work, "switch", "-q", "-c", "pr/borrowed", "pr/clean")
    (work / "borrow.txt").write_text("borrowed\n")
    git(work, "add", ".")
    git(work, "commit", "-q", "-m", "borrowed work on my branch")
    # merge-base(origin/main, pr/borrowed) is the fork point, not origin/main
    borrowed_gate = subprocess.run(
        ["python3", str(REPO / "scripts" / "check_pr_base.py"), "check",
         "--base", cpb.DEFAULT_BASE, "--rev", "pr/borrowed", "--cwd", str(work)],
        capture_output=True, text=True, env=ENV)
    assert borrowed_gate.returncode != 0, borrowed_gate.stdout + borrowed_gate.stderr
    assert "foreign commits" in borrowed_gate.stdout or "NOT cut" in borrowed_gate.stdout
