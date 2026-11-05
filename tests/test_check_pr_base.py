"""A PR must be cut from origin/main itself — the foreign-commit gate (issue #845).

Criteria 3 and 5 of #845: the gate fails a PR whose merge-base with
`refs/remotes/origin/main` is not `refs/remotes/origin/main` itself (the branch
carries commits from another PR — the #794 case), naming the foreign commit; and
it stays GREEN for a clean branch that is exactly one commit ahead of
`origin/main` (the negative control). Real commits, real merge-bases.

Issue #1734 makes the one trust boundary explicit: the gate measures against a
FRESH `main`, re-fetching it at measure time rather than trusting a possibly
stale `refs/remotes/origin/main` — and it REFUSES (never passes) when that fetch
fails. A missing tracking ref is therefore no longer "fabricated a pass": when
the remote is reachable the gate restores it by fetching; when the remote is
unreachable the gate refuses with a fetch-failure and never quietly passes.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

import scripts.check_pr_base as cpb  # noqa: E402

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
    """A branch cut from another PR (diverged from current origin/main) fails, #845.

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


def test_a_missing_base_ref_is_restored_by_fetch_not_vice_versa(tmp_path):
    """#1734: a missing tracking ref is re-fetched; it is not a quiet pass either.

    When `refs/remotes/origin/main` is deleted but the remote is reachable, the
    gate now RESTORES it by fetching (the fresh measure wins) and still judges the
    branch — reachable remote, so a branch cut from live main passes.
    """
    work = repo(tmp_path)
    git(work, "switch", "-q", "-c", "pr/clean", "main")
    (work / "clean.txt").write_text("one ahead\n")
    git(work, "add", ".")
    git(work, "commit", "-q", "-m", "one commit ahead, clean")
    git(work, "update-ref", "-d", "refs/remotes/origin/main")
    ok, foreign = cpb.check(work, cpb.DEFAULT_BASE, "pr/clean")
    assert ok is True, foreign
    assert foreign == []
    # and the fetch genuinely restored the ref (the measured sha is the live one)
    assert git(work, "rev-parse", "refs/remotes/origin/main")


def test_a_fetch_failure_refuses_rather_than_passing_stale(tmp_path):
    """#1734 acceptance: a failed fetch must REFUSE, never pass on a stale measure."""
    work = repo(tmp_path)
    git(work, "switch", "-q", "-c", "pr/clean", "main")
    (work / "clean.txt").write_text("one ahead\n")
    git(work, "add", ".")
    git(work, "commit", "-q", "-m", "one commit ahead, clean")
    # make the remote unreachable — the base ref still resolves LOCALLY (the stale
    # measure would look resolvable), so only the fetch-failure path can catch it
    git(work, "remote", "set-url", "origin", str(tmp_path / "gone.git"))
    ok, foreign = cpb.check(work, cpb.DEFAULT_BASE, "pr/clean")
    assert ok is False
    assert foreign and ("could not fetch" in foreign[0] or "does not resolve" in foreign[0])


def test_stale_local_main_is_refreshed_before_the_verdict(tmp_path):
    """#1734 regression: a STALE refs/remotes/origin/main must not drive the verdict.

    Advance origin/main past the clone's snapshot, leave the clone's tracking ref
    stale, then cut a branch from the LIVE tip and confirm the gate re-fetches and
    measures against the live main (its sha appears in the verdict), not the stale
    one.
    """
    work = repo(tmp_path)
    # origin/main advances (a merge / another PR) while this clone is not re-fetched
    git(work, "switch", "-q", "main")
    (work / "advance.txt").write_text("main moved\n")
    git(work, "add", ".")
    git(work, "commit", "-q", "-m", "origin/main advances")
    git(work, "push", "-q", "origin", "main")
    live = git(work, "rev-parse", "main")

    # NOW refresh the clone's tracking ref to the PRE-advance tip: deliberately stale
    git(work, "update-ref", "refs/remotes/origin/main", f"{live}~1")
    stale = git(work, "rev-parse", "refs/remotes/origin/main")
    assert stale != live, "test premise broken: the tracking ref must be stale"

    # a branch cut from the LIVE tip (what a freshly-cloned next lane would sit on)
    git(work, "switch", "-q", "-c", "pr/live-cut", "main")
    (work / "mine.txt").write_text("my lane\n")
    git(work, "add", ".")
    git(work, "commit", "-q", "-m", "cut from the live tip")
    head = git(work, "rev-parse", "HEAD")

    ok, foreign = cpb.check(work, cpb.DEFAULT_BASE, "pr/live-cut")
    lines = cpb.render(ok, cpb.DEFAULT_BASE, "pr/live-cut", foreign, work)
    text = "\n".join(lines)
    assert ok, text
    # the verdict must measure against the LIVE main sha, which it only has after
    # re-fetching the deliberately stale tracking ref (issue #1734)
    assert f"measured against `{cpb.DEFAULT_BASE}` at `{live}`" in text, text


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
