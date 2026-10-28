#!/usr/bin/env python3
"""Arm auto-merge on the PRs that are green-but-unarmed (issue #912).

`allow_auto_merge` is on, `auto-merge.yml` can approve and merge a green PR, and yet PRs sat
`MERGEABLE/BLOCKED` with `auto=none` until somebody ran `gh pr merge --auto` by hand — 32 of 41 open PRs on
one night. The merge intent belongs to the moment a PR is created, not to a sweep an hour later, so this is
the command the producers call (and the one a lane can run over its own open PRs).

What it deliberately does NOT do:

* it never merges anything itself — `gh pr merge --auto` only ARMS a PR, and GitHub (or `auto-merge.yml`)
  performs the merge when the required checks pass;
* it skips a **draft**, because a draft is not a merge candidate and arming it would queue an invisible
  intent (the draft ban is its own rule, #873);
* it skips a PR that is **already armed**, so running it twice is a no-op rather than a churn of API calls.

Usage:
    arm_auto_merge.py report [--repo R] [--author LOGIN] [--gh gh]
    arm_auto_merge.py arm    [--repo R] [--author LOGIN] [--gh gh] [--dry]

Exit codes: 0 ok (including "nothing to arm"), 2 a `gh` call failed.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

BASE_REPO = "asimov-agent/llgenie"
#: Squash, because the repository's own merge is a squash and a PR is one atomic commit anyway.
METHOD = "squash"


def _gh(gh: str, args: list[str]) -> str:
    r = subprocess.run([gh, *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"[arm-auto-merge] {gh} {' '.join(args)} failed ({r.returncode}): {r.stderr.strip()}")
    return r.stdout


def open_prs(gh: str = "gh", repo: str = BASE_REPO, author: str = "", limit: int = 200) -> list[dict]:
    """Every open PR with the three fields that decide whether it should be armed."""
    args = ["pr", "list", "--repo", repo, "--state", "open", "--limit", str(limit),
            "--json", "number,isDraft,autoMergeRequest,author,mergeable"]
    if author:
        args += ["--author", author]
    return json.loads(_gh(gh, args) or "[]")


def unarmed(prs: list[dict]) -> list[dict]:
    """The PRs that are open, not a draft, and carry no `autoMergeRequest` yet.

    A draft is excluded on purpose: arming it would queue a merge intent for something nobody can review,
    and the repository bans draft PRs outright (#873).
    """
    return [pr for pr in prs
            if pr.get("isDraft") is not True and not pr.get("autoMergeRequest")
            and (pr.get("state") or "OPEN").upper() == "OPEN"]


def armed(gh: str, repo: str, pr: int) -> bool:
    """Does this PR now carry a merge intent? Read back — a `gh` call that printed nothing proves nothing."""
    out = _gh(gh, ["pr", "view", str(pr), "--repo", repo, "--json", "autoMergeRequest"])
    return bool(json.loads(out or "{}").get("autoMergeRequest"))


def arm(gh: str, repo: str, pr: int, dry: bool = False) -> bool:
    """Arm one PR, then VERIFY; True only when the merge intent is readable afterwards.

    `gh pr merge --auto` can succeed and change nothing — a repository with auto-merge disabled, a PR that
    became a draft, a permission that only allows the comment. Reporting "armed" from the exit code alone is
    the same class of defect as reading a cancelled run as a failure: the tool's own silence is not the
    state. So the read-back is part of the operation, and a miss is a named failure.
    """
    if dry:
        print(f"[arm-auto-merge] would arm PR #{pr} ({METHOD})")
        return False
    _gh(gh, ["pr", "merge", str(pr), "--repo", repo, "--auto", f"--{METHOD}"])
    if not armed(gh, repo, pr):
        print(f"[arm-auto-merge] FAIL: PR #{pr} still carries no auto-merge intent after `gh pr merge --auto` "
              f"— check that the repository allows auto-merge and the PR is not a draft",
              file=sys.stderr)
        return False
    print(f"[arm-auto-merge] armed PR #{pr} ({METHOD}), verified by reading it back")
    return True


def report(prs: list[dict], repo: str = BASE_REPO) -> str:
    todo = unarmed(prs)
    lines = [f"[arm-auto-merge] {len(prs)} open PR(s) in {repo}: {len(todo)} unarmed, "
             f"{len(prs) - len(todo)} already armed or draft"]
    for pr in sorted(todo, key=lambda p: p.get("number") or 0):
        who = ((pr.get("author") or {}).get("login") or "unknown")
        lines.append(f"  #{pr.get('number')} by @{who} ({pr.get('mergeable') or 'unknown'})")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("report", "arm"):
        p = sub.add_parser(name)
        p.add_argument("--repo", default=BASE_REPO)
        p.add_argument("--author", default="", help="only PRs by this login (a lane arms its own)")
        p.add_argument("--gh", default="gh")
        p.add_argument("--limit", type=int, default=200)
        if name == "arm":
            p.add_argument("--dry", action="store_true", help="print what would be armed, call nothing")
    args = parser.parse_args(argv)

    prs = open_prs(args.gh, args.repo, args.author, args.limit)
    print(report(prs, args.repo))
    if args.command == "report":
        return 0
    missed = [int(pr["number"]) for pr in sorted(unarmed(prs), key=lambda p: p.get("number") or 0)
              if not arm(args.gh, args.repo, int(pr["number"]), dry=args.dry)]
    if missed and not args.dry:
        print(f"[arm-auto-merge] {len(missed)} PR(s) were NOT armed: {missed}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
