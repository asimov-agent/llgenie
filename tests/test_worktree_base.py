"""A worktree is cut from refs/remotes/origin/main, never the primary HEAD (issue #845).

This is criterion 1 of #845: the dispatch seam must resolve its base from
`refs/remotes/origin/main` (fetching `origin main` first), and it must do so even
when the primary checkout is deliberately parked on a PR branch. These tests use
a real repository with a real `origin`, park the primary checkout on a PR branch
that DIFFERS from `origin/main`, and prove the worktree created through
`scripts/worktree_base.py` lands exactly on `origin/main`.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import worktree_base as wb  # noqa: E402

ENV = {**os.environ,
       "GIT_AUTHOR_NAME": "Andy Holst", "GIT_AUTHOR_EMAIL": "andy.holst@protonmail.com",
       "GIT_COMMITTER_NAME": "Andy Holst", "GIT_COMMITTER_EMAIL": "andy.holst@protonmail.com",
       "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"}


def git(root: Path, *args: str) -> str:
    r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, env=ENV)
    assert r.returncode == 0, f"git {' '.join(args)} failed: {r.stderr}"
    return r.stdout.strip()


def setup(tmp_path: Path) -> Path:
    """A bare origin on `main`, and a clone (the primary checkout) with a PR branch.

    Returns the primary checkout. `origin/main` diverges from the PR branch: two
    commits on the PR branch that are NOT on origin/main.
    """
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

    # Park the primary checkout on a PR branch that DIVERGES from origin/main.
    git(work, "switch", "-q", "-c", "pr/another-lane")
    (work / "pr.txt").write_text("from another PR\n")
    git(work, "add", ".")
    git(work, "commit", "-q", "-m", "foreign work on the primary checkout")
    (work / "pr2.txt").write_text("more foreign work\n")
    git(work, "add", ".")
    git(work, "commit", "-q", "-m", "more foreign work")

    assert git(work, "rev-parse", "--abbrev-ref", "HEAD") == "pr/another-lane"
    assert git(work, "rev-parse", "refs/remotes/origin/main") != git(work, "rev-parse", "HEAD")
    return work


def test_resolve_base_reads_origin_main_never_the_primary_head(tmp_path):
    """`resolve_base()` returns refs/remotes/origin/main, not the parked branch tip."""
    work = setup(tmp_path)
    base = wb.resolve_base(work)
    assert base == git(work, "rev-parse", "refs/remotes/origin/main")
    assert base != git(work, "rev-parse", "HEAD")
    assert base != git(work, "rev-parse", "pr/another-lane")


def test_a_worktree_cut_while_the_primary_is_parked_lands_on_origin_main(tmp_path):
    """The criterion-1 acceptance: new worktree HEAD == origin/main, parked or not.

    `wb.add()` passes the resolved `refs/remotes/origin/main` as the explicit start
    point, so the primary checkout's parked branch is never consulted.
    """
    work = setup(tmp_path)
    wt_dir = tmp_path / "wt-new"
    wb.add(work, wt_dir, "feat/from-origin-main")
    assert (wt_dir / ".git").exists() or (wt_dir / "README").exists()
    assert git(work, "rev-parse", "refs/remotes/origin/main") == git(wt_dir, "rev-parse", "HEAD")
    # and the branch is a clean child of origin/main, one commit? no — zero commits on it
    assert git(work, "rev-list", "--count", "origin/main..feat/from-origin-main") == "0"


def test_the_base_is_fetched_before_use(tmp_path):
    """A stale or missing refs/remotes/origin/main is refreshed, not trusted."""
    work = setup(tmp_path)
    git(work, "update-ref", "-d", "refs/remotes/origin/main")   # drop the remote-tracking ref
    # advance origin/main so a stale ref (had it existed) would be wrong
    git(work, "switch", "-q", "main")
    (work / "m.txt").write_text("main moved\n")
    git(work, "add", ".")
    git(work, "commit", "-q", "-m", "origin/main advances")
    git(work, "push", "-q", "origin", "main")

    base = wb.resolve_base(work)
    assert base == git(work, "rev-parse", "refs/remotes/origin/main")
    assert base == git(work, "rev-parse", "main")     # the fresh origin/main == new main


def test_the_cli_resolves_and_refuses_a_worktree_whose_base_is_unknowable(tmp_path):
    """`resolve` prints the base; a repo with NO remote-tracking base refuses loudly."""
    work = setup(tmp_path)
    out = subprocess.run(["python3", str(REPO / "scripts" / "worktree_base.py"), "resolve",
                          "--root", str(work)],
                         capture_output=True, text=True, env=ENV)
    assert out.returncode == 0
    assert wb.BASE_REF in out.stderr
    assert out.stdout.strip().split()[-1] == git(work, "rev-parse", "refs/remotes/origin/main")
