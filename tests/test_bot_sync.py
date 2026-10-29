"""Every bot syncs with latest upstream main before it starts work (issue #303).

Driven through a REAL scratch git repository - a bare "origin" plus two clones - because the thing
under test *is* git plumbing: assert against the commits and the tree, never against a mock.

The rule: the implementer bases a new branch on latest main (`reset`), the fix-bot wants its PR
rebased onto latest main before repairing it (`rebase`), and a conflict is NOT resolved here - it is
reported and left to the rebase-bot (issue #246).
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "bot_sync_main.sh"


def git(*args: str, cwd: Path) -> str:
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    assert r.returncode == 0, f"git {' '.join(args)} failed: {r.stderr}"
    return r.stdout.strip()


def sync(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    env = {**os.environ, "BOT_SYNC_REMOTE": "origin", "BOT_SYNC_BRANCH": "main",
           "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@e", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@e"}
    return subprocess.run(["bash", str(SCRIPT), *args], cwd=cwd, capture_output=True, text=True,
                          env=env)


def scratch(tmp_path: Path, conflict: bool = False) -> tuple[Path, str, str]:
    """A bare origin whose main ADVANCES after a branch has forked from the old tip."""

    def commit(where: Path, name: str, text: str) -> str:
        (where / name).write_text(text)
        git("add", "-A", cwd=where)
        git("commit", "-q", "-m", f"{name}: {text}", cwd=where)
        return git("rev-parse", "HEAD", cwd=where)

    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True)
    work = tmp_path / "work"
    subprocess.run(["git", "clone", "-q", str(origin), str(work)], check=True)
    git("config", "user.name", "t", cwd=work)
    git("config", "user.email", "t@e", cwd=work)
    git("symbolic-ref", "HEAD", "refs/heads/main", cwd=work)          # bare default branch

    a = commit(work, "file.txt", "first\n" if not conflict else "first\n")
    git("push", "-q", "-u", "origin", "main", cwd=work)

    # the bot's branch forks HERE, from the old tip
    git("checkout", "-q", "-b", "agent/issue-7", cwd=work)
    commit(work, "bot.txt", "the bot's work\n")
    if conflict:
        # the bot edits the SAME line main will move - the branch cannot rebase cleanly
        commit(work, "file.txt", "the bot's version\n")

    # meanwhile main advances
    git("checkout", "-q", "main", cwd=work)
    b = commit(work, "file.txt", "main's version\n" if conflict else "first\nmain moved on\n")
    commit(work, "other.txt", "unrelated\n")
    git("push", "-q", "origin", "main", cwd=work)
    latest = git("rev-parse", "origin/main", cwd=work)

    git("checkout", "-q", "agent/issue-7", cwd=work)
    return work, a, latest


def test_rebase_puts_the_branch_on_latest_main(tmp_path):
    work, _old, latest = scratch(tmp_path)
    r = sync("rebase", cwd=work)
    assert r.returncode == 0, r.stderr
    # the branch now CONTAINS latest main, and its own work is still there
    assert git("merge-base", "--is-ancestor", latest, "HEAD", cwd=work) == ""
    assert (work / "bot.txt").exists(), "the bot's own commit was lost"
    assert git("status", "--porcelain", cwd=work) == "", "a clean rebase leaves no dirt"
    assert "rebased" in r.stdout


def test_reset_makes_the_tree_exactly_latest_main(tmp_path):
    work, _old, latest = scratch(tmp_path)
    r = sync("reset", cwd=work)
    assert r.returncode == 0, r.stderr
    assert git("rev-parse", "HEAD", cwd=work) == latest
    assert not (work / "bot.txt").exists(), "reset discards the branch: new work starts clean"


def test_a_conflict_is_reported_and_left_to_the_rebase_bot(tmp_path):
    work, _old, _latest = scratch(tmp_path, conflict=True)
    before = git("rev-parse", "HEAD", cwd=work)
    r = sync("rebase", cwd=work)
    assert r.returncode == 2, f"a conflict must be exit 2, not {r.returncode}"
    assert "rebase-bot" in r.stderr, r.stderr
    # and NOTHING changed: not the commit, and no rebase left in progress
    assert git("rev-parse", "HEAD", cwd=work) == before
    assert not (work / ".git" / "rebase-merge").exists()
    assert not (work / ".git" / "rebase-apply").exists()


def test_an_unreachable_remote_fails_loudly(tmp_path):
    work, _old, _latest = scratch(tmp_path)
    env = {**os.environ, "BOT_SYNC_REMOTE": "no-such-remote", "BOT_SYNC_BRANCH": "main"}
    r = subprocess.run(["bash", str(SCRIPT), "reset"], cwd=work, capture_output=True, text=True,
                       env=env)
    assert r.returncode != 0, "a bot must never proceed on a stale base"
    assert "refusing to start" in r.stderr


def test_an_unknown_mode_is_refused(tmp_path):
    work, _old, _latest = scratch(tmp_path)
    r = sync("sideways", cwd=work)
    assert r.returncode != 0
    assert "usage" in r.stderr


def test_the_bots_wire_the_sync_into_their_workflows():
    """The rule is not a script nobody runs: both bots call it before they start."""
    issue_bot = (REPO / ".github" / "workflows" / "issue-bot.yml").read_text()
    fix_bot = (REPO / ".github" / "workflows" / "fix-bot.yml").read_text()
    assert "bot-sync-main" in issue_bot, "the implementer must sync before opening a PR"
    assert "bot-sync-branch" in fix_bot, "the fix-bot must sync the PR before repairing it"
    mk = (REPO / "Makefile").read_text()
    for target in ("bot-sync-main:", "bot-sync-branch:"):
        assert target in mk, f"{target} is not a make target"


def test_the_base_remote_is_resolved_not_assumed(tmp_path):
    """`git reset --hard` onto the wrong history is worse than a red test (issue #925).

    This bot hard-resets the tree onto `${REMOTE}/main`. In a clone whose `origin` is the owner's FORK, that
    resets onto different history — so the remote is RESOLVED (the one whose URL is the base repository) instead
    of defaulting to `origin`. Driven through a real repository with both remotes, and the fork's main is set
    to a commit the base does not have, so the two answers are distinguishable.
    """

    def commit(where: Path, name: str, text: str) -> str:
        (where / name).write_text(text, encoding="utf-8")
        git("add", "-A", cwd=where)
        git("commit", "-q", "-m", f"{name}: {text}", cwd=where)
        return git("rev-parse", "HEAD", cwd=where)

    base = tmp_path / "base.git"
    fork = tmp_path / "fork.git"
    for bare in (base, fork):
        subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)

    work = tmp_path / "work"
    subprocess.run(["git", "clone", "-q", str(base), str(work)], check=True)
    git("config", "user.name", "t", cwd=work)
    git("config", "user.email", "t@e", cwd=work)
    git("symbolic-ref", "HEAD", "refs/heads/main", cwd=work)
    commit(work, "file.txt", "base\n")
    git("push", "-q", "-u", "origin", "main", cwd=work)

    # the SAME clone carries the fork as `origin` and the base as `upstream` — the layout that bit #925
    git("remote", "rename", "origin", "upstream", cwd=work)
    git("remote", "add", "origin", str(fork), cwd=work)
    fork_tip = git("rev-parse", "HEAD", cwd=work)
    git("push", "-q", "origin", "main", cwd=work)

    # the base moves on; the fork does NOT, so a reset to the fork would leave the tree behind
    base_tip = commit(work, "newer.txt", "the base moved\n")
    git("push", "-q", "upstream", "main", cwd=work)

    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@e",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@e"}
    env.pop("BOT_SYNC_REMOTE", None)          # the whole point: no override, so the script must resolve
    result = subprocess.run(["bash", str(SCRIPT), "reset"], cwd=work, capture_output=True, text=True, env=env)

    assert result.returncode == 0, result.stderr
    assert "base remote: upstream" in result.stdout, result.stdout
    assert git("rev-parse", "HEAD", cwd=work) == base_tip, (
        f"the sync must land on the BASE tip ({base_tip[:7]}), not the fork's ({fork_tip[:7]})")
