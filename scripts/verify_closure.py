#!/usr/bin/env python3
"""Prove a merged PR closed what it claimed (issue #482).

`gh pr merge` succeeds whether or not the body's `closes #n` bound: GitHub parses the keyword, and a body
that names an issue in prose without the keyword (or with a typo) leaves the issue open after the merge.
That is silent — the run is green, the PR is "done", and the issue stays on the board.

This reads the merged PR's own `closingIssuesReferences` and fails, naming the issue, when a claimed
reference is still open. `make auto-merge` calls it right after the merge, so an unbound keyword is a red
run instead of an issue nobody notices (the shape `trending-local-llms` uses as `make verify-closure`).

Commands (stdlib only, the GitHub API only through a `gh` on PATH):
  verify --repo R --pr N [--gh gh]   print every closing reference and its state; exit 1 if one is open
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys


def _gh(gh: str, args: list[str]) -> str:
    r = subprocess.run([gh, *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"[verify-closure] {gh} {' '.join(args)} failed ({r.returncode}): "
                         f"{r.stderr.strip()}")
    return r.stdout


def pr_view(gh: str, repo: str, pr: int) -> dict:
    """The merged PR: its state and the issues its body claims to close."""
    out = _gh(gh, ["pr", "view", str(pr), "--repo", repo,
                   "--json", "state,closingIssuesReferences,mergeCommit"])
    return json.loads(out or "{}")


def issue_state(gh: str, repo: str, num: int) -> str:
    return json.loads(_gh(gh, ["issue", "view", str(num), "--repo", repo, "--json", "state"])
                      or "{}").get("state", "UNKNOWN")


def verify(gh: str, repo: str, pr: int) -> int:
    """0 when every claimed closing reference is closed; 1 (naming it) when one is still open."""
    view = pr_view(gh, repo, pr)
    state = (view.get("state") or "").upper()
    if state != "MERGED":
        print(f"[verify-closure] PR #{pr} is {state or 'UNKNOWN'}, not MERGED: nothing to verify",
              file=sys.stderr)
        return 2
    refs = [r.get("number") for r in (view.get("closingIssuesReferences") or []) if r.get("number")]
    if not refs:
        # A pure chore legitimately closes nothing (AGENTS.md: say so in `Issue:`); say it, do not fail.
        print(f"[verify-closure] PR #{pr} claims no closing issue — nothing to verify")
        return 0
    open_refs = []
    for num in refs:
        st = issue_state(gh, repo, num)
        print(f"[verify-closure] #{num}: {st}")
        if st.upper() != "CLOSED":
            open_refs.append(num)
    if open_refs:
        print(f"[verify-closure] FAIL: PR #{pr} was merged but "
              + ", ".join(f"#{n}" for n in open_refs)
              + " is still open — the closing keyword did not bind", file=sys.stderr)
        return 1
    print(f"[verify-closure] OK: PR #{pr} closed " + ", ".join(f"#{n}" for n in refs))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="verify_closure", description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("verify", help="verify the closing references of a merged PR")
    v.add_argument("--repo", required=True)
    v.add_argument("--pr", type=int, required=True)
    v.add_argument("--gh", default="gh")
    args = p.parse_args(argv)
    return verify(args.gh, args.repo, args.pr)


if __name__ == "__main__":
    raise SystemExit(main())
