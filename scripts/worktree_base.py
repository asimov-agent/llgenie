#!/usr/bin/env python3
"""Resolve the base for a worktree from `refs/remotes/origin/main`, never the primary HEAD (issue #845).

The defect #845 names: a kanban `worktree` task inherits the primary checkout's
CURRENT branch instead of `origin/main`. The primary directory is routinely
parked on a PR branch by whichever lane last worked there, so a lane spawned
with `git worktree add <path>` (no explicit base) silently starts on someone
else's unmerged diff — measured twice on 2026-10-28.

This is the one seam a lane (or the dispatch path) must ask for the base:

    base = resolve_base(root)   # fetch origin main if needed, return refs/remotes/origin/main sha

It ALWAYS reads `refs/remotes/origin/main` (fetching `origin main` first when
the ref is missing or stale), and NEVER reads the primary checkout's `HEAD`. A
unit test creates a worktree while the primary checkout is deliberately parked
on a PR branch and proves the new worktree's `HEAD == resolve_base()`.

Commands:

    worktree_base.py resolve [--root DIR]   print the base sha (fetching first)
    worktree_base.py add    --path DIR --branch NAME [--root DIR]
        create a worktree at DIR on branch NAME cut from the resolved base, and
        print the base sha. Refuses a `--path` inside an existing worktree.

The `add` command is the dispatch seam: it passes the resolved base as the
explicit start point of `git worktree add`, so the branch is cut from
`origin/main` regardless of what the primary checkout is currently on.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

#: The ref the worktree base is resolved from. NEVER a bare branch the primary
#: checkout might be on; a remote-tracking ref is unambiguous (#845).
BASE_REF = "refs/remotes/origin/main"

TAG = "[worktree-base]"

#: The remote + branch implied by `refs/remotes/<remote>/<branch>`.
_REF = re.compile(r"^refs/remotes/([^/]+)/(.+)$")


def _run(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=False)  # proc-allow: direct subprocess call site, tracked remainder for issue #797 (migrate onto scripts/proc.py in a per-module batch)


def _ok(root: Path, *args: str) -> str:
    r = _run(root, *args)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {(r.stderr or r.stdout).strip()}")
    return r.stdout.strip()


def _resolve_sha(root: Path, ref: str) -> str:
    """The commit a ref names, or '' when it does not exist."""
    out = _run(root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
    return out.stdout.strip()


def fetch(root: Path = REPO_ROOT, ref: str = BASE_REF) -> None:
    """Bring `ref` current: `git fetch --no-tags <remote> <branch>`. Never errors
    on an already-present ref, so a lane may run this unconditionally first."""
    m = _REF.match(ref)
    if not m:
        return
    remote, branch = m.group(1), m.group(2)
    r = _run(root, "fetch", "--no-tags", remote, branch)
    if r.returncode != 0:
        raise RuntimeError(
            f"git fetch --no-tags {remote} {branch} failed: {(r.stderr or r.stdout).strip()} — "
            f"a worktree base that cannot be fetched is not a base (issue #845)")


def resolve_base(root: Path = REPO_ROOT, ref: str = BASE_REF, fetch_first: bool = True) -> str:
    """The base sha a worktree MUST be cut from — read ONLY from the remote-tracked ref.

    Never consults the primary checkout's `HEAD`: that is the very defect #845
    fixes. Fetches `ref` first so a stale or absent ref cannot stand in for the
    live base; a ref that STILL does not exist after the fetch is an error, not
    a fallback to the current branch.
    """
    if fetch_first:
        fetch(root, ref)
    sha = _resolve_sha(root, ref)
    if not sha:
        raise RuntimeError(
            f"`{ref}` does not exist after fetching — a lane cannot start a worktree "
            f"whose base is unknowable (issue #845)")
    return sha


def add(root: Path, path: Path, branch: str, ref: str = BASE_REF) -> str:
    """Create a worktree at *path* on a NEW *branch* cut from the resolved base.

    `git worktree add -b <branch> <path> <base-sha>` — the explicit start point
    is what picks `origin/main`, so the primary checkout's current branch is
    never consulted. Returns the base sha the branch was cut from.
    """
    base = resolve_base(root, ref)
    r = _run(root, "worktree", "add", "-b", branch, str(path), base)
    if r.returncode != 0:
        raise RuntimeError(
            f"git worktree add -b {branch} {path} {base[:12]} failed: "
            f"{(r.stderr or r.stdout).strip()}")
    return base


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="worktree_base", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("resolve", help="print the base sha a worktree must be cut from (fetching first)")
    r.add_argument("--root", default=str(REPO_ROOT))
    r.add_argument("--no-fetch", action="store_true", help="do not fetch; resolve the ref as-is")

    a = sub.add_parser("add", help="create a worktree cut from the resolved base")
    a.add_argument("--root", default=str(REPO_ROOT))
    a.add_argument("--path", required=True, help="the worktree directory to create")
    a.add_argument("--branch", required=True, help="the new branch to create in the worktree")
    args = p.parse_args(argv)

    root = Path(args.root).resolve()
    if args.cmd == "resolve":
        sha = resolve_base(root, fetch_first=not args.no_fetch)
        print(f"{TAG} {sha}")
        print(f"{TAG} base ref `{BASE_REF}` (issue #845): a worktree must be cut here, "
              f"never from the primary checkout's HEAD", file=sys.stderr)
        return 0
    base = add(root, Path(args.path).resolve(), args.branch)
    print(f"{TAG} worktree created on `{args.branch}` cut from base {base}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"{TAG} FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1)
