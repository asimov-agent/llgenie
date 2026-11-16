#!/usr/bin/env python3
"""Backfill read: every issue the issue-bot closed as `not_planned` that a merged PR closes.

Measured (issue #2869, 2026-11-16): the issue-bot claimed #2048, discovered open PR #2863
already implemented it, and closed the ISSUE with `state_reason=not_planned` instead of
leaving it for the PR's own closing keyword (#2863 merged 31 minutes later; its `closes #2048`
was a no-op and the implemented issue had been retired as "not planned"). AGENTS.md: "NEVER
close an issue by hand while a PR implements it. The PR closes it on merge" — issue state must
stay evidence about the code, and `not_planned` must keep meaning "no plan".

This is the READ half of that rule: it names every issue the bot closed with
`state_reason=not_planned` that a MERGED PR carries a `closes #` reference to, so the reason can
be corrected to `completed` (as was done by hand for #2048). It reads only — it never PATCHes the
reason; the correction is a human or a future deterministic step, and naming what is wrong is the
lane's first obligation.

How an issue is identified as "the bot closed it":

- the issue is `closed` AND carries the `agent:closed` label (which `apply-verdict`'s close path
  adds on every bot close), OR
- its `closed_by` is the issue-bot actor (`github-actions[bot]`).

An issue is a MATCH when it is closed, bot-closed, and a merged PR (into `main`) carries it in its
`closingIssuesReferences` — GitHub's parse of the body's adjacent closing keyword. The report
prints each match with its CURRENT `state_reason` and flags the ones that must be corrected:
`not_planned` -> `completed`. An issue already carrying `completed` (e.g. #2048 after the manual
correction) is printed as corrected, so the read also proves the remedy landed.

Reads GitHub through `gh` on PATH (or `--gh`); the tests stub it on PATH, the repo's allowance for
an external CLI. `--limit` bounds the recent merged-PR window.

Commands (stdlib only):
  read [--repo R] [--limit N] [--gh gh]   print the backfill matches; exit 0 (a read never fails
                                          the run because the board needs a correction)
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys

BOT_ACTORS = ("github-actions[bot]", "llgenie", "asimov-agent")
DECIDED_LABEL = "agent:closed"
#: The reason a bot-closed issue that a merged PR closes SHOULD carry (AGENTS.md: an implemented
#: issue is closed by its own PR with `completed`, never retired as `not_planned`).
CORRECT_REASON = "completed"


def _gh(gh: str, args: list[str]) -> str:
    r = subprocess.run([gh, *args], capture_output=True, text=True)  # proc-allow: direct subprocess call site, tracked remainder for issue #797 (migrate onto scripts/proc.py in a per-module batch)
    if r.returncode != 0:
        raise SystemExit(f"[issue-close-backfill] {gh} {' '.join(args)} failed ({r.returncode}): "
                         f"{r.stderr.strip()}")
    return r.stdout


def merged_prs_with_closes(gh: str, repo: str, limit: int = 100) -> list[dict]:
    """Recently merged PRs into `main`, keeping only those whose body GitHub parsed as closing an issue."""
    out = _gh(gh, ["pr", "list", "--repo", repo, "--state", "merged", "--base", "main",
                   "--limit", str(limit),
                   "--json", "number,title,mergedAt,closingIssuesReferences,baseRefName"])
    keep = []
    for pr in json.loads(out or "[]") or []:
        refs = (pr.get("closingIssuesReferences") or [])
        if not refs:
            continue
        if (pr.get("baseRefName") or "main") != "main":
            continue
        keep.append({"number": pr["number"], "title": pr.get("title") or "",
                     "mergedAt": pr.get("mergedAt") or "",
                     "closes": [r["number"] for r in refs if isinstance(r, dict) and r.get("number")]})
    return keep


def issue_state(gh: str, repo: str, num: int) -> dict:
    """state, state_reason and labels for one issue — the fields the bot-close test reads."""
    return json.loads(_gh(gh, ["issue", "view", str(num), "--repo", repo,
                               "--json", "state,stateReason,labels,closedBy"]) or "{}")


def bot_closed(issue: dict) -> bool:
    """Whether the issue-bot is the actor that closed it (label, else the closedBy login)."""
    names = [l.get("name") for l in (issue.get("labels") or []) if l.get("name")]
    if DECIDED_LABEL in names:
        return True
    author = (issue.get("closedBy") or {}).get("login") or ""
    return author.lower() in BOT_ACTORS


def reason_title(state_reason: str | None) -> str:
    return (state_reason or "none").replace("_", " ")


def read(repo: str, limit: int = 100, gh: str = "gh") -> list[dict]:
    """Every bot-closed `not_planned` issue a merged PR closes, plus already-corrected matches.

    sorted newest-merged first. Each entry carries the issue number, the correcting PR, the
    issue's CURRENT state_reason and whether it still needs correction.
    """
    matches = []
    for pr in merged_prs_with_closes(gh, repo, limit):
        for num in pr["closes"]:
            issue = issue_state(gh, repo, num)
            state = str(issue.get("state") or "").lower()
            if state != "closed":
                continue
            if not bot_closed(issue):
                continue
            reason = str(issue.get("stateReason") or "").lower()
            matches.append({
                "issue": num,
                "pr": pr["number"],
                "pr_title": pr["title"],
                "merged_at": pr["mergedAt"],
                "state_reason": reason,
                "needs_correction": reason != CORRECT_REASON,
            })
    matches.sort(key=lambda m: m["merged_at"], reverse=True)
    return matches


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="issue_close_backfill")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("read", help="print every bot-closed not_planned issue a merged PR closes")
    r.add_argument("--repo", required=True)
    r.add_argument("--limit", type=int, default=100)
    r.add_argument("--gh", default="gh")

    args = p.parse_args(argv)
    if args.cmd == "read":
        matches = read(args.repo, args.limit, args.gh)
        if not matches:
            print("[issue-close-backfill] no bot-closed issue in the merged window still needs a "
                  "`completed` correction")
            return 0
        print(f"[issue-close-backfill] {len(matches)} bot-closed issue(s) a merged PR closes:")
        for m in matches:
            flag = ("NEEDS-CORRECTION" if m["needs_correction"]
                    else f"corrected ({CORRECT_REASON})")
            print(f"  #{m['issue']:>6} closed as {m['state_reason'] or 'none':<12} by merged "
                  f"PR #{m['pr']} ({m['pr_title']}) — {flag}")
        for m in matches:
            if m["needs_correction"]:
                print(f"[issue-close-backfill] correct #{m['issue']} to `{CORRECT_REASON}` "
                      "(PATCH state_reason), the reason a merged PR's `closes` should have recorded")
        return 0
    p.error("need a command: read")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
