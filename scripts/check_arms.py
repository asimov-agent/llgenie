#!/usr/bin/env python3
"""A finished PR is armed when it is done, not when it is approved (fleet rule 16, issue #873).

The owner's directive: "their skill behavior should always be to set the PRs to automerge when they are done
with the issue/pr work." The producing lane closes its own work; "armed" is the last move, not a chore for the
merger. A finished but unarmed PR is invisible to every `auto-merge` sweep, so the gate exists to make an
unarmed finished PR a named finding rather than a silence.

What this gate audits — every OPEN PR, listed in one call, filtered in code (issue #1021's lesson: never let
`gh` narrow the denominator, or the audited set drifts):

- **must be armed** (`autoMergeRequest != null`): a PR that is not a draft, whose base is the DEFAULT branch
  (only a main-based PR can be armed — `gh pr merge --auto` arms nothing on a stacked base, issue #964), and
  whose state is mergeable (a conflict or an unknown state means it is not "finished" — a PR that cannot merge
  has nothing to arm into).
- **legitimately unarmed, skipped not flagged**: a draft (not finished work); base != default branch (cannot be
  armed, #964); `DIRTY`/`UNKNOWN`/not mergeable (nothing to merge yet).

`report` prints the findings and exits 0 (the board is readable even when it is dirty); `check` exits 1 when any
finished PR is unarmed. Use `--repo OWNER/NAME` and `--default-branch` (default `main`) for forks or release
branches.

Usage
  python3 scripts/check_arms.py report                 # every open PR and its arm state, exit 0
  python3 scripts/check_arms.py check                  # fail (exit 1) on any finished-but-unarmed PR
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys

DEFAULT_BRANCH = "main"


def open_prs(repo: str) -> list[dict]:
    """Every open PR with the fields this gate reads — one list call, filtered in code, never a `--label`."""
    listed = subprocess.run(
        ["gh", "pr", "list", "--repo", repo, "--state", "open", "--limit", "200",
         "--json", "number,title,isDraft,baseRefName,mergeable,autoMergeRequest"],
        capture_output=True, text=True)
    if listed.returncode != 0:
        raise SystemExit(f"[check-arms] FAIL: cannot list PRs: {listed.stderr.strip()}")
    return json.loads(listed.stdout or "[]")


def finished_unarmed(pr: dict, default_branch: str = DEFAULT_BRANCH) -> bool:
    """True when rule 16 says this open PR must carry an arm and does not.

    Draft → not finished. Base != default branch → cannot be armed (issue #964). Not mergeable → nothing to
    merge, so arming is premature. Only a mergeable, non-draft, default-based PR owes `autoMergeRequest`.
    """
    if pr.get("isDraft"):
        return False
    if (pr.get("baseRefName") or "") != default_branch:
        return False
    if (pr.get("mergeable") or "") not in ("MERGEABLE", "CLEAN"):
        return False
    return pr.get("autoMergeRequest") is None


def findings(prs: list[dict], default_branch: str = DEFAULT_BRANCH) -> list[dict]:
    out = []
    for pr in prs:
        if finished_unarmed(pr, default_branch):
            out.append({
                "number": pr["number"],
                "title": pr.get("title") or "",
                "base": pr.get("baseRefName") or "",
            })
    return out


def report(prs: list[dict], default_branch: str = DEFAULT_BRANCH) -> str:
    lines = [f"[check-arms] {len(prs)} open PR(s), default branch `{default_branch}`:"]
    armed = 0
    for pr in sorted(prs, key=lambda p: p["number"]):
        state = "armed" if pr.get("autoMergeRequest") else "unarmed"
        if pr.get("isDraft"):
            state += " (draft)"
        elif pr.get("baseRefName") != default_branch:
            state += " (stacked base, #964)"
        elif pr.get("mergeable") not in ("MERGEABLE", "CLEAN"):
            state += f" (not mergeable: {pr.get('mergeable')})"
        lines.append(f"  #{pr['number']}: {state}")
        if state == "armed":
            armed += 1
    lines.append(f"[check-arms] {armed}/{len(prs)} armed")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "check arms").splitlines()[0])
    parser.add_argument("mode", nargs="?", default="report", choices=("check", "report"))
    parser.add_argument("--repo", default="asimov-agent/llgenie")
    parser.add_argument("--default-branch", default=DEFAULT_BRANCH)
    args = parser.parse_args(argv)

    prs = open_prs(args.repo)
    print(report(prs, args.default_branch))
    if args.mode == "report":
        return 0
    unarmed = findings(prs, args.default_branch)
    if unarmed:
        print("[check-arms] FAIL: finished PR(s) carry no auto-merge in the queue (#873):")
        for pr in unarmed:
            print(f"  #{pr['number']}: {pr['title']}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
