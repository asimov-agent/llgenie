"""The /tmp worktree+probe debris collector, proven safe (issue #2141).

`scripts/reclaim_tmp_worktrees.sh` is the host-side DELETE half of the check-host-space
preflight: it reclaims `/tmp` worktree and probe-tree debris that is provably safe to
delete, on a real repo with real worktrees, and refuses everything that could lose work.

What the script may delete — everything else is reported, never removed:
  * a REGISTERED worktree only when clean AND its HEAD is an ancestor of the base AND it
    has been idle at least MIN_IDLE_MIN;
  * under FORCE=1 a registered worktree may drop the on-main and idle tests but NEVER the
    dirty refusal, and a novel head (not on the base, on no remote branch) is PINNED as
    `refs/reclaimed/<name>` and verified with `git for-each-ref refs/reclaimed` BEFORE the
    tree is removed;
  * DEREGISTERED debris only when its head is pinned: either a pre-made `refs/reclaimed/<name>`
    ref, or — under FORCE — a freshly pinned one. An unpinnable debris head is reported with
    the exact `sudo rm -rf <path>` remedy and NEVER deleted.

The git side is real — a real repo, real worktrees, real `git worktree remove`, real fork
commits — with every file mutated on disk and NOTHING stubbed. The four measured operator
directories (`/tmp/Notification Cache`, `/tmp/hf`, `/tmp/gatepkg`, `/tmp/1898-unzip` shapes)
are reproduced as fixtures under a private scan root and never touched. DRY=1 (the script's
default) never runs the delete path. A live root-owned cache-only repro needs passwordless
sudo (measured: this host requires a password), so the debris proof uses the `.git`-file
worktree-remnant shape, which needs no privilege.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "reclaim_tmp_worktrees.sh"

GIT_ENV = {
    "GIT_AUTHOR_NAME": "Andy Holst",
    "GIT_AUTHOR_EMAIL": "andy.holst@protonmail.com",
    "GIT_COMMITTER_NAME": "Andy Holst",
    "GIT_COMMITTER_EMAIL": "andy.holst@protonmail.com",
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_SYSTEM": "/dev/null",
}

#: the four measured operator directories (issue #2141), reproduced as fixtures.
OPERATOR_DIRS = ["Notification Cache", "hf", "gatepkg", "1898-unzip"]


def _git(cwd: Path, *args: str) -> str:
    env = {**os.environ, **GIT_ENV}
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, env=env)
    assert result.returncode == 0, f"git {' '.join(args)} failed: {result.stderr}"
    return result.stdout.strip()


def _make_repo(tmp_path: Path) -> tuple[Path, Path]:
    """A real repo with a main branch carrying one commit, plus the scan root beside it."""
    repo, scan = tmp_path / "repo", tmp_path / "scan"
    repo.mkdir(); scan.mkdir()
    _git(repo, "init", "-b", "main")
    (repo / "top.txt").write_text("top\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "initial")
    return repo, scan


def _add_maintree(repo: Path, scan: Path, name: str) -> tuple[Path, str]:
    """A clean, on-main, fresh worktree (the reclaimable negative control shape)."""
    path = scan / name
    _git(repo, "worktree", "add", "--detach", str(path), "main")
    return path, _git(path, "rev-parse", "HEAD")


def _add_novel_tree(repo: Path, scan: Path, name: str) -> tuple[Path, str]:
    """A worktree on a NOVEL branch whose head is not on main (the keep/pin shape)."""
    path = scan / name
    _git(repo, "worktree", "add", "-b", name, str(path), "main")
    (path / "new.txt").write_text("new\n")
    _git(path, "add", ".")
    _git(path, "commit", "-m", f"novel work on {name}")
    return path, _git(path, "rev-parse", "HEAD")


def _run(repo: Path, scan: Path, *extra_env: str) -> subprocess.CompletedProcess:
    env = {
        **os.environ, **GIT_ENV,
        "REPO": str(repo),
        "SCAN_ROOT": str(scan),
        "BASE": "main",
        "MIN_IDLE_MIN": "0",
    }
    for kv in extra_env:
        key, _, val = kv.partition("=")
        env[key] = val
    return subprocess.run(["bash", str(SCRIPT)], capture_output=True, text=True, env=env)


def _inodes_free(scan: Path) -> str:
    """The `df -i` free-inode value for the scan root's filesystem, for no-change proof."""
    out = subprocess.run(["df", "-i", str(scan)], capture_output=True, text=True)
    if out.returncode != 0:
        return "?UNKNOWN?"
    return out.stdout.splitlines()[1].split()[3]


def test_dry_deletes_nothing_even_when_every_tree_would_be_reclaimed(tmp_path):
    repo, scan = _make_repo(tmp_path)
    neg, neg_head = _add_maintree(repo, scan, "neg")          # clean + on main + idle
    before = _inodes_free(scan)
    proc = _run(repo, scan, "DRY=1")
    assert proc.returncode == 0, proc.stderr
    assert neg.is_dir(), "DRY=1 must not remove a reclaimable tree"
    assert "would reclaim" in proc.stdout, proc.stdout
    assert "reclaimed " not in proc.stdout, "DRY=1 must only REPORT, never delete"
    assert _inodes_free(scan) == before, "DRY=1 must not change the free-inode count"


def test_refusals_kept_and_negative_control(tmp_path):
    """dirty kept, head-not-on-main kept, active kept — and clean+on-main+idle reclaimed."""
    repo, scan = _make_repo(tmp_path)
    dirty, _ = _add_maintree(repo, scan, "w-dirty")
    (dirty / "uncommitted.txt").write_text("x\n")
    novel, novel_head = _add_novel_tree(repo, scan, "w-novel")
    neg, _ = _add_maintree(repo, scan, "w-neg")

    proc = _run(repo, scan, "DRY=1")                          # MIN_IDLE_MIN=0 -> all idle
    assert proc.returncode == 0, proc.stderr
    assert f"KEEP  {dirty}" in proc.stdout and "uncommitted" in proc.stdout, proc.stdout
    assert f"KEEP  {novel}" in proc.stdout and f"{novel_head[:8]} is NOT on main" in proc.stdout, proc.stdout
    assert "would reclaim" in proc.stdout and str(neg) in proc.stdout, proc.stdout
    assert dirty.is_dir() and novel.is_dir() and neg.is_dir()

    # active (< MIN_IDLE_MIN) is kept when the idle bar is raised
    proc = _run(repo, scan, "MIN_IDLE_MIN=100000", "DRY=1")
    assert f"KEEP  {neg}" in proc.stdout and "active" in proc.stdout, proc.stdout
    assert neg.is_dir()


def test_force_keeps_the_dirty_refusal_but_widens_the_set(tmp_path):
    repo, scan = _make_repo(tmp_path)
    dirty, _ = _add_maintree(repo, scan, "w-dirty")
    (dirty / "uncommitted.txt").write_text("x\n")
    novel, novel_head = _add_novel_tree(repo, scan, "w-novel")

    # FORCE=1 DRY=1: dirty still refused, novel widened to FORCED-but-still-dry (no pin written)
    proc = _run(repo, scan, "FORCE=1", "DRY=1")
    assert proc.returncode == 0, proc.stderr
    assert f"KEEP  {dirty}" in proc.stdout and "uncommitted" in proc.stdout, proc.stdout
    assert f"FORCED {novel}" in proc.stdout, proc.stdout
    assert "PINNED" not in proc.stdout, "DRY=1 must not write a pin ref even under FORCE"
    assert dirty.is_dir() and novel.is_dir(), "FORCE=1 DRY=1 deletes nothing"

    # FORCE=1 real: dirty still kept, novel head pinned as refs/reclaimed/w-novel then removed
    proc = _run(repo, scan, "FORCE=1", "DRY=0")
    assert proc.returncode == 0, proc.stderr
    assert f"KEEP  {dirty}" in proc.stdout and dirty.is_dir(), \
        "FORCE=1 real must keep a dirty tree"
    refs = _git(repo, "for-each-ref", "refs/reclaimed")
    assert "refs/reclaimed/w-novel" in refs and novel_head in refs, \
        "a novel head must be pinned as refs/reclaimed/<name> before forced removal"
    assert "PINNED refs/reclaimed/w-novel" in proc.stdout, proc.stdout
    assert not novel.exists(), "the pinned novel worktree may be removed only after the pin"


def test_debris_pass_excludes_the_four_operator_dirs(tmp_path):
    """The measured operator dirs are reproduced as fixtures and must never be touched."""
    repo, scan = _make_repo(tmp_path)
    for name in OPERATOR_DIRS:
        d = scan / name
        d.mkdir()
        (d / "operator-file.txt").write_text("keep\n")        # asimov-owned real content
    proc = _run(repo, scan, "DRY=1", "FORCE=1")
    assert proc.returncode == 0, proc.stderr
    for name in OPERATOR_DIRS:
        assert name not in proc.stdout, f"operator dir {name} must not be named for reclamation"
        assert (scan / name).is_dir(), f"operator dir {name} must survive"
    assert "would clear" not in proc.stdout and "cleared deregistered" not in proc.stdout


def test_unpinned_debris_head_reported_never_deleted_with_the_sudo_remedy(tmp_path):
    """A deregistered .git-remnant whose head cannot be pinned is kept, with the remedy."""
    repo, scan = _make_repo(tmp_path)
    debris = scan / "unpinned-debris"
    debris.mkdir()
    (debris / ".git").write_text("gitdir: /nonexistent/missing\n")     # shape (a) worktree remnant
    (debris / "leftover.txt").write_text("content\n")
    proc = _run(repo, scan, "FORCE=1", "DRY=0")
    assert proc.returncode == 0, proc.stderr
    assert(f"BLOCKED {debris}" in proc.stdout), proc.stdout
    assert f"sudo rm -rf {debris}" in proc.stdout, \
        "an unpinned-novel debris head must carry the exact `sudo rm -rf <path>` remedy"
    assert debris.is_dir(), "an unpinned-novel debris head must NEVER be deleted"
    assert "cleared deregistered" not in proc.stdout


def test_pinned_debris_head_is_cleared(tmp_path):
    """Deregistered debris IS cleared once its head is pinned as refs/reclaimed/<name>."""
    repo, scan = _make_repo(tmp_path)
    debris = scan / "pinned-debris"
    debris.mkdir()
    (debris / ".git").write_text("gitdir: /nonexistent/missing\n")
    (debris / "stale.txt").write_text("old build output\n")
    maintip = _git(repo, "rev-parse", "main")
    _git(repo, "update-ref", "refs/reclaimed/pinned-debris", maintip)   # a lane pinned it
    proc = _run(repo, scan, "FORCE=1", "DRY=0")
    assert proc.returncode == 0, proc.stderr
    assert f"cleared deregistered debris {debris}" in proc.stdout or \
           f"would clear deregistered debris {debris}" in proc.stdout, proc.stdout
    assert not debris.exists(), "a pinned-head debris dir may be cleared"
    assert "cleared deregistered debris" in proc.stdout, proc.stdout
