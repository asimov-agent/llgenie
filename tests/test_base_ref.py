#!/usr/bin/env python3
"""The base ref is RESOLVED, not assumed (issue #925).

This host has two clone layouts that name the same two repositories differently — `origin` is the base in one
and the owner's fork in the other. A hard-coded `origin/main` therefore compares against a different tree in
half the clones, and the failure it produces reads as a code or registry defect.

These tests drive the real resolver against real git repositories built in `tmp_path`: the point is not the
string it returns, but that it looks at the remotes and says which one it chose.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import base_ref  # noqa: E402  (the real resolver, never a copy)


def git(cwd: Path, *args: str) -> str:
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r.stdout


def clone(tmp_path: Path, remotes: dict[str, str]) -> Path:
    """A repository with a commit and the given remotes; `main` exists locally and as `<remote>/main`."""
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.email", "t@example.com")
    git(repo, "config", "user.name", "t")
    (repo / "f.txt").write_text("one\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "one")
    (repo / "f.txt").write_text("two\n", encoding="utf-8")
    git(repo, "commit", "-q", "-am", "two")
    for name, url in remotes.items():
        git(repo, "remote", "add", name, url)
    # a remote-tracking ref per remote, so `<remote>/main` resolves
    head = git(repo, "rev-parse", "HEAD").strip()
    for name in remotes:
        git(repo, "update-ref", f"refs/remotes/{name}/main", head)
    return repo


BASE = "https://github.com/asimov-agent/llgenie.git"
FORK = "https://github.com/andyholst/llgenie.git"


def test_the_base_remote_is_found_by_url_not_by_name(tmp_path):
    """`origin` = fork, `upstream` = base — the layout that reds a hard-coded `origin/main`."""
    repo = clone(tmp_path, {"origin": FORK, "upstream": BASE})

    assert base_ref.base_remote(cwd=str(repo)) == "upstream"
    assert base_ref.resolve_base(cwd=str(repo), quiet=True) == "upstream/main"


def test_the_other_layout_resolves_to_origin(tmp_path):
    """`origin` = base, `fork` = the owner's — the layout CI runs in."""
    repo = clone(tmp_path, {"origin": BASE, "fork": FORK})

    assert base_ref.base_remote(cwd=str(repo)) == "origin"
    assert base_ref.resolve_base(cwd=str(repo), quiet=True) == "origin/main"


def test_an_explicit_ref_is_used_verbatim(tmp_path):
    """A caller that pins the comparison keeps it, as long as the ref exists."""
    repo = clone(tmp_path, {"origin": FORK, "upstream": BASE})

    assert base_ref.resolve_base(cwd=str(repo), explicit="origin/main", quiet=True) == "origin/main"


def test_it_says_which_ref_it_chose_when_that_is_not_origin(tmp_path, capsys):
    """A surprising result must name its own cause, or the next reader re-derives it."""
    repo = clone(tmp_path, {"origin": FORK, "upstream": BASE})

    with_ref = base_ref.resolve_base(cwd=str(repo))
    err = capsys.readouterr().err

    assert with_ref == "upstream/main"
    assert "using `upstream/main`" in err, err
    assert "not `origin`" in err, err


def test_no_configured_base_falls_back_and_says_so(tmp_path, capsys):
    """No remotes at all: a local answer beats nothing, but it must not pretend to be the base branch."""
    repo = clone(tmp_path, {})

    ref = base_ref.resolve_base(cwd=str(repo))
    err = capsys.readouterr().err

    assert ref != "origin/main"
    assert "no base branch is configured" in err, err


def test_the_worktree_sweep_resolves_its_base_too():
    """The sweep that DELETES worktrees must judge ancestry against the base, not against a fork (#925).

    `scripts/worktree_prune.py` decided "this branch is merged" by testing `git merge-base --is-ancestor <tip>
    origin/main`. In a clone whose `origin` is the owner's fork that is a different tree — and the consequence
    is a deleted worktree, not a red test.
    """
    sys.path.insert(0, str(REPO / "scripts"))
    import worktree_prune  # noqa: E402

    assert worktree_prune.DEFAULT_BASE is None, (
        "a module-level default cannot be right for both clone layouts; it must be resolved")
    resolved = worktree_prune.default_base()
    assert resolved, resolved
    # and it is a ref this clone actually has, resolved from the remotes rather than assumed
    assert subprocess.run(["git", "rev-parse", "--verify", "--quiet", f"{resolved}^{{commit}}"],
                          cwd=str(REPO), capture_output=True).returncode == 0, resolved


def test_the_rebase_bot_rebases_onto_the_resolved_base(tmp_path):
    """`git rebase $ORIGIN/main` replays a PR's commit onto whatever `origin` is (issue #925).

    In the fork-`origin` layout that is different history, and a rebase bot replaying onto it produces a PR
    that looks rebased and is not on the base. The script must resolve the remote, and the prompt it writes for
    the conflict agent must name the ref it actually used.
    """
    script = (REPO / "scripts" / "rebase_bot.sh").read_text()

    assert "base_ref.py" in script, "the rebase bot must resolve its base remote (issue #925)"
    assert "ORIGIN=\"${ORIGIN:-origin}\"" not in script, (
        "a bare `origin` default is what rebased onto the fork in the maintainer layout")
    assert 'rebase "$ORIGIN/main"' in script, script[-800:]
    assert "rebasing onto ${ORIGIN}/main" in script, (
        "the conflict prompt must name the ref that is actually used, not a hard-coded one")
