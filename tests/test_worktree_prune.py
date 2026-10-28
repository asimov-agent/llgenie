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
import shutil
import sys
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


def _runtime_stub(tmp_path: Path, *, cleans: bool) -> Path:
    """A `docker` on PATH for the debris step — it deletes what the mount names, or refuses.

    The sweep deletes root-owned debris with `docker run --rm -v <parent>:/wt <image> rm -rf /wt/<name>`
    (#759). `cleans=True` performs that delete (the host's own user can remove its own fixture files, so
    the outcome is the same as a root delete); `cleans=False` answers like an engine that cannot mount
    the path — which must leave a reported leftover, never a traceback.
    """
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    script = bin_dir / "docker"
    if cleans:
        body = (
            "#!/bin/sh\n"
            'mount=""\n'
            'last=""\n'
            'for arg in "$@"; do last="$arg"; case "$arg" in *:/wt) mount="${arg%:/wt}";; esac; done\n'
            '[ -n "$mount" ] || exit 1\n'
            'case "$last" in /wt/*) ;; *) exit 1;; esac\n'
            'rm -rf "${mount}/${last#/wt/}"\n'
        )
    else:
        body = '#!/bin/sh\necho "docker: not available" >&2\nexit 1\n'
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


def _run(
    tmp_path: Path,
    work: Path,
    prs: list[dict],
    *args: str,
    fails: bool = False,
    runtime: str | None = None,
) -> subprocess.CompletedProcess:
    """Run the prune for real, with the stubbed `gh` (and optionally a stubbed runtime) first on PATH.

    `runtime` is `"cleans"`/`"refuses"` to control the debris step; `None` names a runtime that is not
    installed at all (`RUNTIME=llgenie-no-such-engine`), so the sweep must report a leftover rather than
    drive whatever engine the host happens to have.
    """
    bin_dir = _gh_stub(tmp_path, prs, fails=fails)
    if runtime is not None:
        _runtime_stub(tmp_path, cleans=runtime == "cleans")
    env = {
        **os.environ,
        **GIT_ENV,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "RUNTIME": "docker" if runtime is not None else "llgenie-no-such-engine",
    }
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


def test_one_run_prunes_every_merged_branch_and_its_worktree(tmp_path):
    """Two merged branches and their worktrees are gone after ONE run (issue #570).

    Measured on a real checkout: the first run removed both worktrees and deleted neither branch
    ("pruned 0 branches, 2 worktrees"), and a second run deleted the branches. A prune that needs two
    runs is a prune that reports the wrong thing about the tree it just touched.
    """

    # Given two squash-merged branches, each with its own clean worktree
    work = _repo(tmp_path)
    prs = []
    trees = []
    for i, name in enumerate(("feat/one", "feat/two"), start=1):
        squash = _merged_branch(work, name)
        tree = tmp_path / f"wt-{i}"
        _git(work, "worktree", "add", str(tree), name)
        trees.append(tree)
        prs.append(_pr(i, name, "MERGED", squash))

    # When  the prune runs ONCE
    result = _run(tmp_path, work, prs)

    # Then  both worktrees and both branches are gone, and the summary says so
    assert result.returncode == 0, result.stderr
    for tree in trees:
        assert not tree.exists(), f"{tree} survived"
    heads = _git(work, "for-each-ref", "--format=%(refname:short)", "refs/heads")
    assert "feat/one" not in heads and "feat/two" not in heads, heads
    assert "pruned 2 branches, 2 worktrees" in result.stdout, result.stdout


def test_a_detached_worktree_of_a_merged_branch_is_pruned_in_one_run(tmp_path):
    """A worktree git reports as DETACHED still holds its branch: match it, remove it, delete it.

    Measured on the real checkout (issue #570): the plan said `would prune 1 branches, 0 worktrees`
    for a branch that HAS a worktree, `git worktree remove` was skipped (path None), and
    `git branch -D` then failed with "used by worktree at …", so the sweep exited 2 forever.
    """

    # Given a squash-merged branch whose worktree is attached to the branch but checked out detached
    work = _repo(tmp_path)
    squash = _merged_branch(work, "fix/detached")
    tree = tmp_path / "wt-detached"
    _git(work, "worktree", "add", str(tree), "fix/detached")
    tip = _git(tree, "rev-parse", "HEAD")
    _git(tree, "checkout", "--detach", tip)
    assert "detached" in _git(work, "worktree", "list", "--porcelain")

    # When  the prune runs once
    result = _run(tmp_path, work, [_pr(9, "fix/detached", "MERGED", squash)])

    # Then  it succeeds, and BOTH the worktree and the branch are gone
    assert result.returncode == 0, result.stdout + result.stderr
    assert not tree.exists(), "the detached worktree must be removed with its branch"
    heads = _git(work, "for-each-ref", "--format=%(refname:short)", "refs/heads")
    assert "fix/detached" not in heads, heads

    # And   the summary never promises "0 worktrees" for a branch that has one
    assert "pruned 1 branches, 1 worktrees" in result.stdout, result.stdout


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


def test_a_detached_worktree_on_the_merged_tip_is_removed_with_its_branch(tmp_path):
    """A detached worktree parked on the merged branch's tip IS that branch's checkout (issue #570).

    The old rule kept the directory and deleted the branch, which leaves a checkout git associates with
    nothing — the stranding the module's own apply() warns about. The merge licenses both: the work is
    on the base, and the directory is that work's checkout.
    """

    # Given a detached-HEAD worktree at a merged branch's tip
    work = _repo(tmp_path)
    squash = _merged_branch(work, "feat/detached")
    tip = _git(work, "rev-parse", "feat/detached")
    tree = tmp_path / "wt-detached"
    _git(work, "worktree", "add", "--detach", str(tree), tip)

    # When  the prune runs
    result = _run(tmp_path, work, [_pr(12, "feat/detached", "MERGED", squash)])

    # Then  the worktree and the branch are BOTH gone, and the plan never promised 0 worktrees
    assert result.returncode == 0, result.stderr
    assert not tree.exists(), "the merged branch's own checkout must not be stranded"
    assert "feat/detached" not in _git(work, "for-each-ref", "--format=%(refname:short)", "refs/heads")
    assert "pruned 1 branches, 1 worktrees" in result.stdout, result.stdout


def test_a_detached_worktree_on_another_commit_is_never_removed(tmp_path):
    """A detached worktree parked somewhere else holds no branch of ours, so nothing licenses it."""

    # Given a detached-HEAD worktree at an unrelated commit, and a merged branch with no worktree
    work = _repo(tmp_path)
    squash = _merged_branch(work, "feat/elsewhere")
    root = _git(work, "rev-list", "--max-parents=0", "HEAD")
    _git(work, "worktree", "add", "--detach", str(tmp_path / "wt-old"), root)
    tree = tmp_path / "wt-old"

    # When  the prune runs for the merged branch
    result = _run(tmp_path, work, [_pr(13, "feat/elsewhere", "MERGED", squash)])

    # Then  the unrelated detached worktree survives and the branch is still pruned
    assert result.returncode == 0, result.stderr
    assert tree.is_dir(), "a detached worktree on an unrelated commit is not ours to delete"
    assert "feat/elsewhere" not in _git(work, "for-each-ref", "--format=%(refname:short)", "refs/heads")


def test_apply_turns_a_branch_held_by_a_worktree_into_a_keep(tmp_path, monkeypatch):
    """A refusal naming a worktree we may not touch is a KEEP, never an Error 2 (issue #593).

    git's own refusal is the only evidence for this association (the porcelain listing shows such a
    worktree as pure `detached` with no branch line), so the decision is driven here against the real
    `apply()` and the exact message git produces.
    """

    # Given a merged branch whose delete is refused by a worktree that is NOT our debris
    sys.path.insert(0, str(REPO / "scripts"))
    import worktree_prune as wp

    def fake_git(args, *, cwd=None, check=True):
        if args[:2] == ["branch", "-D"]:
            raise wp.PruneError("cannot delete branch 'feat/x' used by worktree at '/wt/held'")
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(wp, "_git", fake_git)
    monkeypatch.setattr(wp, "_detached_and_clean", lambda path, cwd=None: False)
    decisions = [wp.Decision("feat/x", "prune", "PR #1 merged, its merge commit is on origin/main", pr=1)]

    # When  the plan is applied
    outcome = wp.apply(decisions)

    # Then  nothing errors, the branch is kept, and the reason names the holding worktree
    assert outcome.errors == [], outcome.errors
    assert decisions[0].action == "keep", decisions[0]
    assert "/wt/held" in decisions[0].reason, decisions[0].reason
    assert outcome.removed_branches == []


def test_apply_removes_a_clean_detached_holder_and_retries_once(tmp_path, monkeypatch):
    """Removable debris is removed first, then the delete is retried exactly once."""

    # Given a refusal by a clean, branch-less, detached worktree
    sys.path.insert(0, str(REPO / "scripts"))
    import worktree_prune as wp

    calls: list[list[str]] = []
    refusals = {"left": 1}

    def fake_git(args, *, cwd=None, check=True):
        calls.append(list(args))
        if args[:2] == ["branch", "-D"] and refusals["left"]:
            refusals["left"] -= 1
            raise wp.PruneError("cannot delete branch 'feat/x' used by worktree at '/wt/clean'")
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(wp, "_git", fake_git)
    monkeypatch.setattr(wp, "_detached_and_clean", lambda path, cwd=None: True)
    decisions = [wp.Decision("feat/x", "prune", "PR #1 merged, its merge commit is on origin/main", pr=1)]

    # When  the plan is applied
    outcome = wp.apply(decisions)

    # Then  the worktree is removed, the branch is deleted, and the retry happened ONCE
    assert outcome.errors == [], outcome.errors
    assert ["worktree", "remove", "/wt/clean"] in calls, calls
    assert calls.count(["branch", "-D", "feat/x"]) == 2, calls
    assert outcome.removed_worktrees == ["/wt/clean"]
    assert outcome.removed_branches == ["feat/x"]


def test_apply_still_errors_when_a_refusal_names_no_worktree(tmp_path, monkeypatch):
    """A refusal we cannot attribute is not silenced: it stays an error, loudly."""

    # Given a `branch -D` failure that names no worktree
    sys.path.insert(0, str(REPO / "scripts"))
    import worktree_prune as wp

    def fake_git(args, *, cwd=None, check=True):
        if args[:2] == ["branch", "-D"]:
            raise wp.PruneError("cannot delete branch 'feat/x': not fully merged")
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(wp, "_git", fake_git)
    decisions = [wp.Decision("feat/x", "prune", "merged", pr=1)]

    # When  the plan is applied
    outcome = wp.apply(decisions)

    # Then  it is an error and the branch is not reported as pruned
    assert outcome.errors and "could not delete the branch" in outcome.errors[0], outcome.errors
    assert outcome.removed_branches == []


def test_the_refusal_helpers_read_gits_own_evidence(tmp_path):
    """The retry path acts only on a worktree git reports as detached, branch-less and clean."""

    # Given a repository with one named worktree and one clean detached worktree
    work = _repo(tmp_path)
    _git(work, "switch", "-c", "feat/named", "main")
    _git(work, "switch", "main")          # the main checkout gives the branch up to its own worktree
    named = tmp_path / "wt-named"
    _git(work, "worktree", "add", str(named), "feat/named")
    detached = tmp_path / "wt-detached"
    _git(work, "worktree", "add", "--detach", str(detached), _git(work, "rev-parse", "main"))

    # When  a refusal message names one of them
    sys.path.insert(0, str(REPO / "scripts"))
    import worktree_prune as wp
    message = f"error: cannot delete branch 'feat/x' used by worktree at '{named}'"

    # Then  the path is read out of git's own message
    assert wp._refused_by_worktree(message) == str(named)
    assert wp._refused_by_worktree("error: branch not found") is None

    # And   only the detached, branch-less, clean one is removable debris
    assert wp._detached_and_clean(str(detached), cwd=str(work)) is True
    assert wp._detached_and_clean(str(named), cwd=str(work)) is False, "a named worktree is another checkout"
    (detached / "dirty.txt").write_text("wip\n")
    assert wp._detached_and_clean(str(detached), cwd=str(work)) is False, "a dirty worktree is never debris"


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


def test_a_worktree_that_cannot_be_removed_is_reported_as_a_leftover_and_exits_zero(tmp_path):
    """A failed removal is a named leftover, not `Error 2`: the reason, the path and the fix are printed.

    Measured on a real checkout (issue #759): the first non-dry run unregistered the worktree, left the
    directory behind and exited 2, so the sweep read as broken while only a directory was left.
    """

    # Given a merged-PR branch whose worktree git refuses to remove (it is locked)
    work = _repo(tmp_path)
    squash = _merged_branch(work, "feat/locked")
    tree = tmp_path / "wt-locked"
    _git(work, "worktree", "add", str(tree), "feat/locked")
    _git(work, "worktree", "lock", str(tree))

    # When  the prune runs
    result = _run(tmp_path, work, [_pr(15, "feat/locked", "MERGED", squash)], runtime="refuses")

    # Then  it exits 0, names the directory as a leftover with the command that clears it, and says
    #       why the branch was kept instead of failing the whole sweep
    assert result.returncode == 0, result.stdout + result.stderr
    assert tree.is_dir()
    assert f"[worktree-prune] leftover {tree}" in result.stdout, result.stdout
    assert "clear it with:" in result.stdout
    assert "docker run --rm -v" in result.stdout
    assert "1 leftover(s)" in result.stdout
    assert "FAILED" not in result.stderr
    assert "feat/locked" in _git(work, "for-each-ref", "--format=%(refname:short)", "refs/heads")


def _left_over_worktree(tmp_path: Path, branch: str, tree_name: str) -> tuple[Path, Path]:
    """A real repository plus a worktree whose git registration is gone while its directory stays.

    That is the state `git worktree remove` leaves when it unregisters the worktree and *then* fails to
    delete its contents (root-owned files from a containerized `make test-unit`, #433). It cannot be
    produced by the planner — `git status` inside a worktree with no admin dir fails, and the planner
    keeps a worktree it cannot read — so the test hands `apply()` the decision the plan made before the
    removal and lets the real sweep recover (#759).
    """
    work = _repo(tmp_path)
    _merged_branch(work, branch)
    tree = tmp_path / tree_name
    _git(work, "worktree", "add", str(tree), branch)
    admin = work / ".git" / "worktrees" / tree.name
    assert admin.is_dir()
    shutil.rmtree(admin)
    assert tree.is_dir() and str(tree) not in _git(work, "worktree", "list")
    return work, tree


def _import_sweep():
    """The sweep's own module, so a test can call `apply()`/`render()` directly."""
    sys.path.insert(0, str(REPO / "scripts"))
    import worktree_prune  # noqa: PLC0415 — the module under test, imported once per test

    return worktree_prune


def test_apply_reports_a_surviving_directory_and_still_deletes_its_branch(tmp_path, monkeypatch):
    """The measured half-done run: the worktree is unregistered, its directory survives, the branch goes.

    `pruned 0 branches, 1 worktrees` and `Error 2` was the old answer (issue #759). It must be a leftover
    naming the directory and the command that clears it, with the branch delete done, not skipped.
    """

    # Given a merged branch whose worktree directory survived its own unregistration
    work, tree = _left_over_worktree(tmp_path, "feat/debris", "wt-debris")
    sweep = _import_sweep()
    monkeypatch.setenv("RUNTIME", "llgenie-no-such-engine")

    # When  apply() runs for real on the decision the planner made
    decision = sweep.Decision("feat/debris", "prune", "PR #17 merged", pr=17, path=str(tree))
    outcome = sweep.apply([decision], cwd=str(work))

    # Then  the directory is a leftover with its reason and its clearing command, and the branch is gone
    assert not outcome.errors, outcome.errors
    assert [leftover.path for leftover in outcome.leftovers] == [str(tree)]
    assert "could not be deleted" in outcome.leftovers[0].reason
    assert outcome.leftovers[0].command.startswith("llgenie-no-such-engine run --rm -v ")
    assert f"{tree.parent}:/wt" in outcome.leftovers[0].command
    assert f"rm -rf /wt/{tree.name}" in outcome.leftovers[0].command
    assert outcome.removed_branches == ["feat/debris"]
    assert "feat/debris" not in _git(work, "for-each-ref", "--format=%(refname:short)", "refs/heads")
    assert tree.is_dir()

    # And the printed plan says so, in the summary and in its own line
    printed = "\n".join(sweep.render(outcome, dry=False, base="origin/main"))
    assert f"[worktree-prune] leftover {tree} — the directory could not be deleted" in printed
    assert "clear it with:" in printed
    assert "1 leftover(s)" in printed


def test_root_owned_debris_is_cleared_through_the_container_engine(tmp_path, monkeypatch, capsys):
    """Where the container engine answers, the sweep deletes the debris itself and retries the removal.

    The engine is the one that created the root-owned files (#433), so it is the one asked to delete
    them: `docker run --rm -v <parent>:/wt <image> rm -rf /wt/<name>`, then the removal again (#759).
    No leftover and no human step when that works.
    """

    # Given a surviving worktree directory and an engine that deletes what the mount names
    work, tree = _left_over_worktree(tmp_path, "feat/rootown", "wt-rootown")
    _runtime_stub(tmp_path, cleans=True)
    monkeypatch.setenv("PATH", f"{tmp_path / 'bin'}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("RUNTIME", "docker")
    sweep = _import_sweep()

    # When  apply() runs for real
    decision = sweep.Decision("feat/rootown", "prune", "PR #18 merged", pr=18, path=str(tree))
    outcome = sweep.apply([decision], cwd=str(work))

    # Then  the directory is gone, the branch is gone, and nothing is reported as left over
    assert not outcome.errors, outcome.errors
    assert outcome.leftovers == []
    assert outcome.removed_worktrees == [str(tree)]
    assert not tree.exists(), f"{tree} survived"
    assert "cleared the root-owned debris" in capsys.readouterr().out
    assert "feat/rootown" not in _git(work, "for-each-ref", "--format=%(refname:short)", "refs/heads")


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
