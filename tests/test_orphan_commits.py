#!/usr/bin/env python3
"""Tests for scripts/check_orphan_commits.py (issue #442).

The shape measured on #413: `feat/bot-model-1017`'s only PR (#410) merged, a fix was committed to
that SAME branch after the merge, and nothing noticed — the commit rode no PR for a day. Each
scenario is a REAL local git repo (a bare `origin` plus a clone, real commits, real pushes); the
merged/open PR map is a PATH-stubbed fake `gh` serving canned `gh api pulls` rows — the
established fixture pattern, fixture data, no mocked logic.
"""
from __future__ import annotations

import json
import stat
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.check_orphan_commits import check  # noqa: E402

REPO = "owner/repo"


class Board(NamedTuple):
    work: Path  # the clone everything is committed/pushed through
    head_a: str  # the merged PR's recorded head sha


def _git(*argv: str, cwd: Path) -> str:
    r = subprocess.run(["git", *argv], cwd=str(cwd), capture_output=True, text=True, check=True)
    return r.stdout.strip()


def _mk_repo(tmp_path: Path) -> Board:
    """A bare `origin` and a clone with main + branch feat/x whose tip is the merged PR head."""
    origin = tmp_path / "origin.git"
    origin.mkdir()
    subprocess.run(["git", "init", "--bare", "-q", "-b", "main", str(origin)], check=True)
    work = tmp_path / "work"
    subprocess.run(["git", "-c", "init.defaultBranch=main", "clone", "-q", str(origin), str(work)],
                   check=True)
    for k, v in (("user.name", "Test Author"), ("user.email", "author@example.com")):
        _git("config", k, v, cwd=work)
    (work / "README.md").write_text("# repo\n")
    _git("add", "README.md", cwd=work)
    _git("commit", "-qm", "initial", cwd=work)
    _git("push", "-qu", "origin", "main", cwd=work)
    _git("checkout", "-qb", "feat/x", cwd=work)
    (work / "fix.md").write_text("merged head\n")
    _git("add", "fix.md", cwd=work)
    _git("commit", "-qm", "the fix that merged", cwd=work)
    _git("push", "-qu", "origin", "feat/x", cwd=work)
    head_a = _git("rev-parse", "HEAD", cwd=work)
    _git("checkout", "-q", "main", cwd=work)
    return Board(work=work, head_a=head_a)


def _merged_row(head_sha: str, number: int = 10) -> dict:
    return {
        "number": number,
        "merged_at": "2026-10-20T11:00:47Z",
        "head": {"ref": "feat/x", "sha": head_sha, "repo": {"full_name": REPO}},
    }


def _fake_gh(tmp_path: Path, merged: list[dict], opened: list[dict],
             fail_open: bool = False, fail_merged: bool = False) -> str:
    """A PATH-stub `gh` serving canned `gh api pulls` rows for the two state queries."""
    (tmp_path / "merged.json").write_text(json.dumps(merged))
    (tmp_path / "open.json").write_text(json.dumps(opened))
    merged_arm = "echo 'gh: HTTP 403' >&2; exit 1" if fail_merged else f"cat {tmp_path / 'merged.json'}"
    open_arm = "echo 'gh: HTTP 403' >&2; exit 1" if fail_open else f"cat {tmp_path / 'open.json'}"
    gh = tmp_path / "gh"
    gh.write_text(f"""#!/bin/sh
case "$*" in
  *state=closed*) {merged_arm} ;;
  *state=open*) {open_arm} ;;
  *) echo '[]' ;;
esac
""")
    gh.chmod(gh.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return str(gh)


def _advance_branch(work: Path) -> str:
    """A post-merge push onto the merged PR's branch — the exact #413/feat-bot-model-1017 shape."""
    _git("checkout", "-q", "feat/x", cwd=work)
    (work / "late-fix.md").write_text("committed after the merge\n")
    _git("add", "late-fix.md", cwd=work)
    _git("commit", "-qm", "the fix for the next issue", cwd=work)
    _git("push", "-q", "origin", "feat/x", cwd=work)
    late = _git("rev-parse", "--short", "HEAD", cwd=work)
    _git("checkout", "-q", "main", cwd=work)
    return late


def _check(work: Path, gh: str, baseline: Path | None = None) -> tuple[int, str]:
    argv = [sys.executable, str(REPO_ROOT / "scripts" / "check_orphan_commits.py"),
            "--repo", REPO, "--gh", gh, "--cwd", str(work)]
    if baseline is not None:
        argv += ["--baseline", str(baseline)]
    r = subprocess.run(argv, capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def test_post_merge_push_is_an_orphan_named_with_branch_sha_and_pr(tmp_path):
    board = _mk_repo(tmp_path)
    late = _advance_branch(board.work)
    gh = _fake_gh(tmp_path, [_merged_row(board.head_a)], [])
    rc, out = _check(board.work, gh)
    assert rc != 0
    assert f"orphan: feat/x {late}" in out
    assert "merged PR #10" in out and "merged 2026-10-20T11:00:47Z" in out
    assert "the fix for the next issue" in out


def test_tip_equal_to_merged_head_is_residue_not_orphan(tmp_path):
    board = _mk_repo(tmp_path)
    gh = _fake_gh(tmp_path, [_merged_row(board.head_a)], [])
    rc, out = _check(board.work, gh)
    assert rc == 0
    assert "orphan:" not in out


def test_open_pr_covering_the_branch_is_in_flight_not_orphan(tmp_path):
    board = _mk_repo(tmp_path)
    _advance_branch(board.work)
    open_row = {"number": 42, "head": {"ref": "feat/x", "sha": "irrelevant",
                                       "repo": {"full_name": REPO}}}
    gh = _fake_gh(tmp_path, [_merged_row(board.head_a)], [open_row])
    rc, out = _check(board.work, gh)
    assert rc == 0
    assert "orphan:" not in out


def test_tip_already_ancestor_of_main_has_landed(tmp_path):
    board = _mk_repo(tmp_path)
    _advance_branch(board.work)
    _git("merge", "-q", "--no-ff", "origin/feat/x", cwd=board.work)  # the branch's work landed
    _git("push", "-q", "origin", "main", cwd=board.work)
    gh = _fake_gh(tmp_path, [_merged_row(board.head_a)], [])
    rc, out = _check(board.work, gh)
    assert rc == 0
    assert "orphan:" not in out


def test_commit_landed_by_squash_is_not_an_orphan(tmp_path):
    """The repo's real merge shape: a SQUASH lands the patch, so the branch sha never appears in
    main by ancestry — git cherry patch-id must still see it as landed."""
    board = _mk_repo(tmp_path)
    late = _advance_branch(board.work)
    _git("cherry-pick", "origin/feat/x", cwd=board.work)  # squash stand-in: same patch, new sha
    _git("push", "-q", "origin", "main", cwd=board.work)
    gh = _fake_gh(tmp_path, [_merged_row(board.head_a)], [])
    rc, out = _check(board.work, gh)
    assert rc == 0
    assert late not in out  # the landed-by-patch commit is not named


def test_branch_without_any_pr_is_not_in_the_merged_shape(tmp_path):
    board = _mk_repo(tmp_path)
    _git("checkout", "-qb", "scratch/other", cwd=board.work)
    (board.work / "s.md").write_text("no PR ever\n")
    _git("add", "s.md", cwd=board.work)
    _git("commit", "-qm", "scratch", cwd=board.work)
    _git("push", "-qu", "origin", "scratch/other", cwd=board.work)
    _git("checkout", "-q", "main", cwd=board.work)
    gh = _fake_gh(tmp_path, [_merged_row(board.head_a)], [])
    rc, out = _check(board.work, gh)
    assert rc == 0  # the guard checks the MERGED-PR-branch shape; unrelated branches are out of scope


def test_merged_read_refusal_is_loud(tmp_path):
    board = _mk_repo(tmp_path)
    gh = _fake_gh(tmp_path, [_merged_row(board.head_a)], [], fail_merged=True)
    with pytest.raises(SystemExit) as excinfo:
        check(repo=REPO, gh=gh, cwd=board.work)
    assert "cannot read" in str(excinfo.value) and "state=closed" in str(excinfo.value)


def test_open_read_refusal_is_loud(tmp_path):
    board = _mk_repo(tmp_path)
    gh = _fake_gh(tmp_path, [_merged_row(board.head_a)], [], fail_open=True)
    with pytest.raises(SystemExit) as excinfo:
        check(repo=REPO, gh=gh, cwd=board.work)
    assert "cannot read open PRs" in str(excinfo.value)


def test_filed_baseline_residue_is_named_but_tolerated(tmp_path):
    """Issue #442's green-baseline rule: a residue already filed on the board (its branch
    deletion is consent-gated cleanup) is STILL named, yet does not fail the run."""
    board = _mk_repo(tmp_path)
    late = _advance_branch(board.work)
    gh = _fake_gh(tmp_path, [_merged_row(board.head_a, number=10)], [])
    baseline = tmp_path / "baseline.json"
    baseline.write_text(json.dumps([{"branch": "feat/x", "merged_pr": 10}]))
    rc, out = _check(board.work, gh, baseline)
    assert rc == 0
    assert f"orphan: feat/x {late}" in out  # naming is never traded for silence
    assert "tolerated baseline residue" in out


def test_baseline_entry_for_a_different_merged_pr_shelters_nothing(tmp_path):
    """Branches are reused in this repo: a baseline entry keyed to an OLD merged PR gives no
    shelter when the same branch carries a NEW merged PR's orphan."""
    board = _mk_repo(tmp_path)
    late = _advance_branch(board.work)
    gh = _fake_gh(tmp_path, [_merged_row(board.head_a, number=10)], [])
    baseline = tmp_path / "baseline.json"
    baseline.write_text(json.dumps([{"branch": "feat/x", "merged_pr": 99}]))
    rc, out = _check(board.work, gh, baseline)
    assert rc != 0
    assert f"orphan: feat/x {late}" in out
    assert "tolerated" not in out


def test_malformed_baseline_fails_loud(tmp_path):
    board = _mk_repo(tmp_path)
    gh = _fake_gh(tmp_path, [_merged_row(board.head_a)], [])
    baseline = tmp_path / "baseline.json"
    baseline.write_text("{not json")
    with pytest.raises(SystemExit) as excinfo:
        check(repo=REPO, gh=gh, cwd=board.work, baseline_path=baseline)
    assert "not valid JSON" in str(excinfo.value)
