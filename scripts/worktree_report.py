#!/usr/bin/env python3
"""Report every worktree and mutate nothing — the preflight a host bot runs before it starts (issue #794).

A host bot starts work with no idea what the bench looks like: `AGENTS.md` mandates a fresh
worktree per agent, and no bot step ever sees the merge that would let it clean up, so leftover
directories accumulate unseen (measured 2026-10-28 on the owner's host: 37 worktrees, 7 on a branch
already in `origin/main`, 23 off-main with no open PR). The neighbouring target, `make
worktree-prune`, DELETES directories and cannot see uncommitted work, so it is the wrong thing for an
unattended run to reach for.

This is the measurement, so nobody has to guess. Per entry of `git worktree list --porcelain` it
prints:

  * the path and the branch (`detached` when the entry holds no branch),
  * `merged-into-main` — a real `git merge-base --is-ancestor <head> <base>`,
  * `open-pr` — a real `gh pr list` for the repository, keyed by the branch the PR's head names,
  * `dirty` — a real `git status --porcelain` inside that worktree (a path that no longer exists
    reads `yes`, because a missing tree cannot be proven clean),

then a summary line counting the total, the merged-and-pr-less entries, the off-main-and-pr-less
entries and the dirty ones. It runs no `git worktree remove`, no `git worktree prune` and no
`git branch -D`: the report can be run at any time, including while work is in flight.

Exit 0 even when nothing is stale. Exit 2 when a measurement fails (a bad base ref, a failing `gh`),
because an unreadable state is not a clean state and must never read as one.

Usage:
    python3 scripts/worktree_report.py [--repo OWNER/NAME] [--base origin/main] [--root PATH]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

#: The base a branch tip is tested against, unless `--base` says otherwise.
DEFAULT_BASE = "origin/main"

#: The slug `gh` reads, unless `--repo` says otherwise.
DEFAULT_REPO = "asimov-agent/llgenie"

#: How many open PRs one lookup reads. The repository has never held 500 at once.
PR_LIMIT = "500"

#: The label every line carries, so a report is greppable in a long job log.
TAG = "[worktree-report]"

#: Exit code for a failed measurement — never a silent "nothing is stale".
EXIT_FAILURE = 2

class ReportError(RuntimeError):
    """A measurement that must stop the report: a failed git step or a failed PR lookup."""


@dataclass
class Worktree:
    """One entry of `git worktree list --porcelain`."""

    path: str
    head: str = ""
    branch: str | None = None
    bare: bool = False
    prunable: bool = False
    #: The repository's main checkout — the first entry git prints. Never a cleanup candidate.
    primary: bool = False


@dataclass
class Row:
    """One printed row: the four measured facts for a worktree."""

    worktree: Worktree
    merged: bool
    pr_number: int | None
    dirty: bool

    @property
    def stale(self) -> bool:
        """Merged into the base, owned by no open PR, and not the main checkout."""
        return self.merged and self.pr_number is None and not self.worktree.primary

    @property
    def off_main_without_pr(self) -> bool:
        """Not merged and owned by no open PR — an abandoned attempt, a human's decision."""
        return not self.merged and self.pr_number is None and not self.worktree.primary


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(args, cwd=str(cwd), capture_output=True, text=True)  # proc-allow: direct subprocess call site, tracked remainder for issue #797 (migrate onto scripts/proc.py in a per-module batch)
    except OSError as exc:  # the executable itself is missing
        raise ReportError(f"{args[0]} could not be run: {exc}") from exc


def _git(cwd: Path, *args: str) -> str:
    """Run one `git` step, failing loudly with the step named."""
    proc = _run(["git", *args], cwd)
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip().splitlines()
        raise ReportError(f"git {' '.join(args)} failed ({proc.returncode}): {detail[-1] if detail else 'no output'}")
    return proc.stdout


def parse_porcelain(text: str) -> list[Worktree]:
    """Parse `git worktree list --porcelain` into entries, in the order git prints them."""
    entries: list[Worktree] = []
    current: Worktree | None = None
    for line in text.splitlines():
        if not line.strip():
            continue
        key, _, value = line.partition(" ")
        if key == "worktree":
            current = Worktree(path=value, primary=not entries)
            entries.append(current)
        elif current is None:
            continue
        elif key == "HEAD":
            current.head = value
        elif key == "branch":
            prefix = "refs/heads/"
            current.branch = value[len(prefix):] if value.startswith(prefix) else value
        elif key == "bare":
            current.bare = True
        elif key == "prunable":
            current.prunable = True
    return entries


def open_prs(repo: str, cwd: Path) -> dict[str, int]:
    """`{head branch: PR number}` for every open PR, from one real `gh` call."""
    proc = _run(["gh", "pr", "list", "--repo", repo, "--state", "open", "--limit", PR_LIMIT,
                 "--json", "headRefName,number"], cwd)
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip().splitlines()
        raise ReportError(
            f"gh pr list --repo {repo} --state open failed ({proc.returncode}): "
            f"{detail[-1] if detail else 'no output'}")
    try:
        payload = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError as exc:
        raise ReportError(f"gh pr list returned unparseable JSON: {exc}") from exc
    out: dict[str, int] = {}
    for pr in payload:
        name = pr.get("headRefName")
        if isinstance(name, str) and name:
            out[name] = int(pr.get("number") or 0)
    return out


def is_ancestor(cwd: Path, head: str, base: str) -> bool:
    """Is *head* reachable from *base*? A real `merge-base --is-ancestor`, exit 1 = no, 2+ = broken."""
    if not head:
        return False
    proc = _run(["git", "merge-base", "--is-ancestor", head, base], cwd)
    if proc.returncode == 0:
        return True
    if proc.returncode == 1:
        return False
    detail = (proc.stderr or proc.stdout).strip().splitlines()
    raise ReportError(
        f"git merge-base --is-ancestor {head} {base} failed ({proc.returncode}): "
        f"{detail[-1] if detail else 'no output'}")


def is_dirty(path: Path) -> bool:
    """Does the worktree at *path* hold a change? A path that is gone counts as dirty."""
    if not path.is_dir():
        return True
    proc = _run(["git", "status", "--porcelain"], path)
    if proc.returncode != 0:
        return True
    return bool(proc.stdout.strip())


def collect(root: Path, base: str, repo: str) -> list[Row]:
    """Measure every worktree: the one read path the printer and the tests share."""
    worktrees = parse_porcelain(_git(root, "worktree", "list", "--porcelain"))
    prs = open_prs(repo, root)
    rows: list[Row] = []
    for wt in worktrees:
        rows.append(Row(
            worktree=wt,
            merged=is_ancestor(root, wt.head, base),
            pr_number=prs.get(wt.branch) if wt.branch else None,
            dirty=is_dirty(Path(wt.path)),
        ))
    return rows


def render(rows: list[Row], base: str, repo: str) -> list[str]:
    """The report as lines: one per worktree, then the summary. Pure, so it is testable."""
    lines = [f"{TAG} {len(rows)} worktrees (base {base}, repo {repo})"]
    for row in rows:
        wt = row.worktree
        lines.append(
            f"{TAG} {wt.path}"
            f"  branch={wt.branch or 'detached'}"
            f"  merged-into-main={'yes' if row.merged else 'no'}"
            f"  open-pr={'yes' if row.pr_number is not None else 'no'}"
            f"  dirty={'yes' if row.dirty else 'no'}"
            + ("  (main checkout)" if wt.primary else "")
            + ("  (path missing)" if not Path(wt.path).is_dir() else "")
            + ("  (prunable)" if wt.prunable else ""))
    stale = sum(1 for row in rows if row.stale)
    off_main = sum(1 for row in rows if row.off_main_without_pr)
    dirty = sum(1 for row in rows if row.dirty)
    lines.append(
        f"{TAG} summary total={len(rows)} stale={stale} off-main-no-pr={off_main} dirty={dirty}")
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--repo", default=DEFAULT_REPO, help=f"owner/name gh reads (default {DEFAULT_REPO})")
    parser.add_argument("--base", default=DEFAULT_BASE, help=f"base ref ancestry is tested against (default {DEFAULT_BASE})")
    parser.add_argument("--root", default=".", help="the checkout whose worktrees are reported (default .)")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    try:
        rows = collect(root, args.base, args.repo)
    except ReportError as exc:
        print(f"{TAG} FAILED: {exc}", file=sys.stderr)
        print(f"{TAG} an unreadable state is not a clean state — nothing was pruned, nothing was reported", file=sys.stderr)
        return EXIT_FAILURE
    for line in render(rows, args.base, args.repo):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
