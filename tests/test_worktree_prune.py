"""Which worktree and branch a prune may remove — decided by the merged PR, proven by its merge commit (#431).

This repository squash-merges, so a merged branch's tip is NEVER an ancestor of `main`: `git branch
--merged` and `git merge-base --is-ancestor` call landed work unmerged forever, and `git branch -d`
refuses it. That is why the eligibility in `scripts/worktree_prune.py` is read from the PR, and why
the fixture here **squash-merges for real** instead of pretending a branch is merged.

The git side is real: a real repository, real worktrees, real `git worktree remove` and
`git branch -D`. Only `gh` is stubbed on `PATH` — the repo's documented allowance for an external
CLI — so the logic runs against controlled API answers while every mutation happens on disk.

The cases that matter are the ones a naive prune gets wrong:

  * a squash-merged branch whose worktree is clean — removed, and the branch with it;
  * a dirty worktree — never force-removed, the branch kept with it;
  * a CLOSED PR and a branch with no PR — kept, because neither is evidence of merged work;
  * a MERGED PR whose merge commit is not on the base — kept, because GitHub says merged while the
    base says otherwise;
  * the repository's main checkout and a detached worktree — untouchable;
  * `--dry` — prints the plan and mutates nothing;
  * a failing `gh` — exits non-zero and prunes nothing.
"""
from __future__ import annotations

import json
import os
import stat
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

GIT_ENV = {
    "GIT_AUTHOR_NAME": "Andy Holst",
    "GIT_AUTHOR_EMAIL": "andy.holst@protonmail.com",
    "GIT_COMMITTER_NAME": "Andy Holst",
    "GIT_COMMITTER_EMAIL": "andy.holst@protonmail.com",
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_SYSTEM": "/dev/null",
}


def _git(cwd: Path, *args: str) -> str:
    """One real git command in the fixture, with an identity so commits always succeed."""
    env = {**os.environ, **GIT_ENV}
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, env=env)
    assert result.returncode == 0, f"git {' '.join(args)} failed: {result.stderr}"
    return result.stdout.strip()


def _gh_stub(tmp_path: Path, prs: list[dict], *, fails: bool = False) -> Path:
    """A `gh` on PATH that answers `pr list` from a JSON file (or fails, loudly)."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    (tmp_path / "prs.json").write_text(json.dumps(prs))
    script = bin_dir / "gh"
    if fails:
        body = '#!/bin/sh\necho "HTTP 502: bad gateway" >&2\nexit 1\n'
    else:
        body = f'#!/bin/sh\ncat "{tmp_path / "prs.json"}"\n'
    script.write_text(body)
    script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return bin_dir


def _repo(tmp_path: Path) -> Path:
    """A real repository whose `origin` is a real bare repo, on `main`."""
    origin = tmp_path / "origin.git"
    work = tmp_path / "work"
    origin.mkdir()
    work.mkdir()
    _git(origin, "init", "--bare", "-b", "main", ".")
    _git(work, "init", "-b", "main", ".")
    (work / "README.md").write_text("fixture\n")
    _git(work, "add", "README.md")
    _git(work, "commit", "-m", "seed")
    _git(work, "remote", "add", "origin", str(origin))
    _git(work, "push", "-u", "origin", "main")
    return work


def _merged_branch(work: Path, branch: str) -> str:
    """Create `branch`, commit on it, and squash-merge it into `main` — the state that defeats ancestry.

    Returns the squash commit's oid: the PR's `mergeCommit`, and the ONLY proof the branch landed.
    """
    _git(work, "switch", "-c", branch, "main")
    name = branch.replace("/", "-")
    (work / f"{name}.txt").write_text("landed\n")
    _git(work, "add", f"{name}.txt")
    _git(work, "commit", "-m", f"feat: {branch}")
    tip = _git(work, "rev-parse", "HEAD")
    _git(work, "switch", "main")
    _git(work, "merge", "--squash", branch)
    _git(work, "commit", "-m", f"feat: {branch} (#1)")
    squash = _git(work, "rev-parse", "HEAD")
    _git(work, "push", "origin", "main")
    assert subprocess.run(["git", "merge-base", "--is-ancestor", tip, "origin/main"], cwd=work).returncode != 0, (
        "the fixture must squash-merge, so the branch tip is NOT an ancestor"
    )
    return squash


def _pr(number: int, head: str, state: str, merge_oid: str = "") -> dict:
    return {
        "number": number,
        "state": state,
        "headRefName": head,
        "mergeCommit": {"oid": merge_oid} if merge_oid else None,
    }


def _run(tmp_path: Path, work: Path, prs: list[dict], *args: str, fails: bool = False) -> subprocess.CompletedProcess:
    """Run the prune for real, with the stubbed `gh` first on PATH."""
    bin_dir = _gh_stub(tmp_path, prs, fails=fails)
    env = {**os.environ, **GIT_ENV, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}
    return subprocess.run(
        ["python3", str(REPO / "scripts" / "worktree_prune.py"), "--repo", "asimov-agent/llgenie", *args],
        cwd=work,
        capture_output=True,
        text=True,
        env=env,
    )


def test_prunes_a_squash_merged_branch_and_its_clean_worktree(tmp_path):
    """A squash-merged branch and its clean worktree are removed, and the PR is named."""

    # Given a squash-merged branch (its tip is NOT an ancestor of main) with a clean worktree
    work = _repo(tmp_path)
    squash = _merged_branch(work, "feat/x")
    tree = tmp_path / "wt-x"
    _git(work, "worktree", "add", str(tree), "feat/x")
    assert tree.is_dir()

    # When  the prune runs with that PR's merge commit on the base
    result = _run(tmp_path, work, [_pr(7, "feat/x", "MERGED", squash)])

    # Then  the worktree is gone, the branch is gone, and the PR number is in the output
    assert result.returncode == 0, result.stderr
    assert not tree.exists()
    assert "feat/x" not in _git(work, "for-each-ref", "--format=%(refname:short)", "refs/heads")
    assert "PR #7" in result.stdout
    assert "pruned 1 branches, 1 worktrees" in result.stdout


def test_a_dirty_worktree_is_kept_and_says_so(tmp_path):
    """An uncommitted change blocks both the worktree removal and the branch deletion."""

    # Given a merged-PR branch whose worktree carries an uncommitted change
    work = _repo(tmp_path)
    squash = _merged_branch(work, "feat/dirty")
    tree = tmp_path / "wt-dirty"
    _git(work, "worktree", "add", str(tree), "feat/dirty")
    (tree / "wip.txt").write_text("uncommitted\n")

    # When  the prune runs
    result = _run(tmp_path, work, [_pr(8, "feat/dirty", "MERGED", squash)])

    # Then  the worktree and the branch both survive, and the reason names the dirty worktree
    assert result.returncode == 0, result.stderr
    assert tree.is_dir()
    assert "feat/dirty" in _git(work, "for-each-ref", "--format=%(refname:short)", "refs/heads")
    assert "keep feat/dirty" in result.stdout
    assert "uncommitted changes" in result.stdout


def test_a_closed_or_prless_branch_is_kept(tmp_path):
    """Neither a CLOSED PR nor no PR is evidence that a branch's work landed."""

    # Given a branch naming a CLOSED unmerged PR and a branch naming no PR at all
    work = _repo(tmp_path)
    _git(work, "switch", "-c", "fix/closed", "main")
    (work / "closed.txt").write_text("x\n")
    _git(work, "add", "closed.txt")
    _git(work, "commit", "-m", "fix: closed")
    _git(work, "switch", "-c", "scratch/no-pr", "main")
    (work / "scratch.txt").write_text("y\n")
    _git(work, "add", "scratch.txt")
    _git(work, "commit", "-m", "tmp")
    _git(work, "switch", "main")

    # When  the prune runs
    result = _run(tmp_path, work, [_pr(9, "fix/closed", "CLOSED")])

    # Then  both branches survive and each reason names its case
    assert result.returncode == 0, result.stderr
    heads = _git(work, "for-each-ref", "--format=%(refname:short)", "refs/heads")
    assert "fix/closed" in heads
    assert "scratch/no-pr" in heads
    assert "PR #9 is CLOSED (unmerged)" in result.stdout
    assert "names no PR at all" in result.stdout


def test_a_merge_commit_off_the_base_is_kept(tmp_path):
    """GitHub saying MERGED is not enough: the merge commit must be on the base."""

    # Given a MERGED PR whose merge commit is the branch's own tip, which main never received
    work = _repo(tmp_path)
    _git(work, "switch", "-c", "feat/elsewhere", "main")
    (work / "elsewhere.txt").write_text("z\n")
    _git(work, "add", "elsewhere.txt")
    _git(work, "commit", "-m", "feat: elsewhere")
    tip = _git(work, "rev-parse", "HEAD")
    _git(work, "switch", "main")

    # When  the prune runs against that PR record
    result = _run(tmp_path, work, [_pr(10, "feat/elsewhere", "MERGED", tip)])

    # Then  the branch survives and the reason says the merge commit is not on the base
    assert result.returncode == 0, result.stderr
    assert "feat/elsewhere" in _git(work, "for-each-ref", "--format=%(refname:short)", "refs/heads")
    assert "is not on origin/main" in result.stdout


def test_the_main_checkout_is_never_removed(tmp_path):
    """The repository's own checkout is out of scope, whatever its branch's history says."""

    # Given a merged-PR branch checked out in the repository's main checkout
    work = _repo(tmp_path)
    squash = _merged_branch(work, "feat/in-main")
    _git(work, "switch", "feat/in-main")
    assert _git(work, "rev-parse", "--abbrev-ref", "HEAD") == "feat/in-main"

    # When  the prune runs from inside that checkout
    result = _run(tmp_path, work, [_pr(11, "feat/in-main", "MERGED", squash)])

    # Then  the checkout still exists, still holds the branch, and the reason says why
    assert result.returncode == 0, result.stderr
    assert work.is_dir()
    assert _git(work, "rev-parse", "--abbrev-ref", "HEAD") == "feat/in-main"
    assert "checked out in the repository's main checkout" in result.stdout


def test_a_detached_worktree_is_never_removed(tmp_path):
    """A detached worktree holds no branch, so no merge can license deleting it."""

    # Given a detached-HEAD worktree at a merged branch's tip
    work = _repo(tmp_path)
    squash = _merged_branch(work, "feat/detached")
    tip = _git(work, "rev-parse", "feat/detached")
    tree = tmp_path / "wt-detached"
    _git(work, "worktree", "add", "--detach", str(tree), tip)

    # When  the prune runs
    result = _run(tmp_path, work, [_pr(12, "feat/detached", "MERGED", squash)])

    # Then  the detached worktree still exists, and the branch itself is pruned
    assert result.returncode == 0, result.stderr
    assert tree.is_dir()
    assert "feat/detached" not in _git(work, "for-each-ref", "--format=%(refname:short)", "refs/heads")


def test_dry_run_prunes_nothing_and_prints_the_plan(tmp_path):
    """A dry run names what it would prune and leaves the repository untouched."""

    # Given a merged-PR branch with a clean worktree
    work = _repo(tmp_path)
    squash = _merged_branch(work, "feat/dry")
    tree = tmp_path / "wt-dry"
    _git(work, "worktree", "add", str(tree), "feat/dry")

    # When  the prune runs with --dry
    result = _run(tmp_path, work, [_pr(13, "feat/dry", "MERGED", squash)], "--dry")

    # Then  the plan names it, and the branch and worktree both survive
    assert result.returncode == 0, result.stderr
    assert "would prune feat/dry" in result.stdout
    assert tree.is_dir()
    assert "feat/dry" in _git(work, "for-each-ref", "--format=%(refname:short)", "refs/heads")


def test_a_worktree_that_cannot_be_removed_keeps_its_branch_and_exits_nonzero(tmp_path):
    """A failed worktree removal stops at that branch: deleting the branch first would strand the tree."""

    # Given a merged-PR branch whose worktree git refuses to remove (it is locked)
    work = _repo(tmp_path)
    squash = _merged_branch(work, "feat/locked")
    tree = tmp_path / "wt-locked"
    _git(work, "worktree", "add", str(tree), "feat/locked")
    _git(work, "worktree", "lock", str(tree))

    # When  the prune runs
    result = _run(tmp_path, work, [_pr(15, "feat/locked", "MERGED", squash)])

    # Then  it exits 2, the worktree survives, the BRANCH survives, and the failure is named
    assert result.returncode == 2, result.stdout
    assert tree.is_dir()
    assert "feat/locked" in _git(work, "for-each-ref", "--format=%(refname:short)", "refs/heads")
    assert "FAILED" in result.stderr
    assert "could not remove worktree" in result.stderr


def test_the_worktree_the_run_is_in_is_never_removed(tmp_path):
    """git cannot remove the directory it is standing in, so that worktree is reported, not attempted."""

    # Given a merged-PR branch whose worktree is where the prune will run from
    work = _repo(tmp_path)
    squash = _merged_branch(work, "feat/self")
    tree = tmp_path / "wt-self"
    _git(work, "worktree", "add", str(tree), "feat/self")

    # When  the prune runs FROM that worktree
    result = _run(tmp_path, tree, [_pr(16, "feat/self", "MERGED", squash)])

    # Then  it exits 0, keeps the worktree and the branch, and says why
    assert result.returncode == 0, result.stderr
    assert tree.is_dir()
    assert "feat/self" in _git(work, "for-each-ref", "--format=%(refname:short)", "refs/heads")
    assert "is the worktree this run is executing in" in result.stdout


def test_a_failed_pr_lookup_prunes_nothing_and_exits_nonzero(tmp_path):
    """A failing `gh` is a loud failure, never a run that prunes from a partial answer."""

    # Given a merged-PR branch and a `gh` that answers with an error
    work = _repo(tmp_path)
    squash = _merged_branch(work, "feat/lookup")
    tree = tmp_path / "wt-lookup"
    _git(work, "worktree", "add", str(tree), "feat/lookup")

    # When  the prune runs
    result = _run(tmp_path, work, [_pr(14, "feat/lookup", "MERGED", squash)], fails=True)

    # Then  it exits 2, names the gh failure, and mutates nothing
    assert result.returncode == 2
    assert "FAILED" in result.stderr
    assert "gh pr list" in result.stderr
    assert tree.is_dir()
    assert "feat/lookup" in _git(work, "for-each-ref", "--format=%(refname:short)", "refs/heads")


def test_the_make_target_is_phony_documented_and_forwards_dry():
    """The target is a phony make target, carries a help line, is in the README, and forwards DRY."""

    # Given the real checkout's Makefile and README
    makefile = (REPO / "Makefile").read_text()
    readme = (REPO / "README.md").read_text()

    # When  the target and the .PHONY block (a `\`-continued block, not one line) are read
    lines = makefile.splitlines()
    target = [line for line in lines if line.startswith("worktree-prune:")]
    phony: list[str] = []
    collecting = False
    for line in lines:
        if line.startswith(".PHONY:"):
            collecting = True
        elif collecting and not line.startswith("\t"):
            if line.rstrip().endswith("\\"):
                phony.append(line)
                continue
            phony.append(line)
            collecting = False
            continue
        if collecting:
            phony.append(line.rstrip("\\"))
            collecting = line.rstrip().endswith("\\")

    # Then  the target exists with a help line, is phony, forwards DRY, and is documented
    assert len(target) == 1, "make worktree-prune must exist exactly once"
    assert "##" in target[0], "the target needs a `##` line `make help` reads"
    assert any("worktree-prune" in line for line in phony), "worktree-prune must be declared .PHONY"
    assert "scripts/worktree_prune.py" in makefile
    assert "$(if $(DRY),--dry,)" in makefile
    # REPO is the Makefile's checkout path (line 40: `REPO := $(shell pwd)`); gh rejects a path
    # where it wants owner/name, so the slug seam is SLUG and the recipe must never pass REPO.
    assert "--repo $(if $(SLUG),$(SLUG),asimov-agent/llgenie)" in makefile
    assert "worktree_prune.py --repo $(if $(REPO)" not in makefile
    assert "worktree-prune" in readme, "make check-docs fails a user-facing target missing from the README"
