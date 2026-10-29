#!/usr/bin/env python3
"""A hold must name its remedy: `do-not-merge` without a resolving issue is abandonment (issue #948).

The owner's ruling: never flag a PR `do-not-merge` unless it is **totally wrong or conflicting with something
concrete**, and if a lane does, it **files the fix issue that makes the tag removable and says so where a reader
can see it**. A bot-implemented PR can never carry the tag by default — it means "there is a known defect with a
tracked remedy", never "this lane would rather not".

`mergeStateStatus` reads `BLOCKED` for a hold with a remedy and for one without, so no existing gate can tell the
two apart. This one can: for every open PR carrying the label, the PR BODY or any COMMENT must name an issue
(`#123`, `resolves #123`, `fixes #123`). Absent that, the tag has no exit condition, and the check fails naming
the PR and the two ways out.

Usage
  python3 scripts/check_holds.py check                  # fail (exit 1) on any hold with no named issue
  python3 scripts/check_holds.py report                 # same information, exit 0
  python3 scripts/check_holds.py check --fixture f.json # offline: the tests seed this shape, no network

The fixture shape is the one the live path builds:
  [{"number": 904, "title": "…", "body": "…", "comments": [{"body": "resolves #948"}]}]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

LABEL = "do-not-merge"
# `#123` anywhere in prose, but not a bare "#" or a markdown heading ("## Problem" has no digits).
ISSUE_REF = re.compile(r"(?<![\w#])#(\d{1,6})(?!\d)")
# The REMEDY has to be a resolve-verb next to an issue number. A PR body mentions a dozen issues in passing
# ("blocked on #767, see #892"), so "any #N" would pass every hold ever placed - measured on this repo: all three
# held PRs named issues and none of them named a remedy for the HOLD.
REMEDY = re.compile(
    r"(?:resolves?|resolved\s+by|resolving\s+issue|fixed\s+by|fixes|unblocked?\s+by|blocked\s+by|until|"
    r"lifted\s+(?:when|by|once)|exit\s+condition|pending|awaiting)\s*:?\s*#(\d{1,6})", re.IGNORECASE)
# Kept for the message the operator reads ("the hold says which issue lifts it"), never for matching: a broad
# "any #N in a comment that mentions the hold" fallback was measured and dropped - it let #904 pass on seven
# numbers at once, which is the same imprecision the whole issue is about.
HOLD_WORD = re.compile(r"do-not-merge|\bhold\b|holding", re.IGNORECASE)


def held_prs(repo: str) -> list[dict]:
    """Every open PR carrying the label, with its comments — one list call and one comments call each."""
    listed = subprocess.run(
        ["gh", "pr", "list", "--repo", repo, "--state", "open", "--label", LABEL, "--limit", "100",
         "--json", "number,title,body"],
        capture_output=True, text=True)
    if listed.returncode != 0:
        raise SystemExit(f"[check-holds] FAIL: cannot list PRs: {listed.stderr.strip()}")
    prs = json.loads(listed.stdout or "[]")
    for pr in prs:
        comments = subprocess.run(
            ["gh", "api", f"repos/{repo}/issues/{pr['number']}/comments", "--paginate",
             "--jq", "[.[]|{body}]"],
            capture_output=True, text=True)
        pr["comments"] = json.loads(comments.stdout or "[]") if comments.returncode == 0 else []
    return prs


def remedy_issues(pr: dict) -> list[int]:
    """The issues named as the REMEDY for the hold.

    The verb list covers the shapes the board actually uses, measured rather than guessed: #904 states its remedy
    as "resolving issue #949" and "lifting condition unchanged: the five criteria in #949", and a first version
    keyed only on `resolves`/`blocked by` reported it as NO REMEDY - a false red on a hold that was properly
    documented. A passing mention (`supersedes #786, see #892`) matches nothing here, which is the point: on this
    board every held PR names issues in passing and none of them named a remedy for the HOLD.
    """
    found: list[int] = []
    for text in [pr.get("body") or ""] + [comment.get("body") or "" for comment in pr.get("comments") or []]:
        candidates = [int(match.group(1)) for match in REMEDY.finditer(text)]
        for number in candidates:
            if number != pr.get("number") and number not in found:
                found.append(number)
    return found


def hold_comments(pr: dict) -> list[str]:
    """The comments that are actually about the hold — those a reader would look to for the exit condition."""
    return [comment.get("body") or "" for comment in pr.get("comments") or []
            if HOLD_WORD.search(comment.get("body") or "")]


def issue_numbers(pr: dict) -> list[int]:
    """Issue numbers named in the body or in any comment — the remedy the tag promises."""
    texts = [pr.get("body") or ""]
    texts += [comment.get("body") or "" for comment in pr.get("comments") or []]
    found: list[int] = []
    for text in texts:
        for match in ISSUE_REF.finditer(text):
            number = int(match.group(1))
            if number != pr.get("number") and number not in found:
                found.append(number)
    return found


def findings(prs: list[dict]) -> list[dict]:
    """A held PR with no named issue is the finding: the tag has no condition under which it comes off."""
    out = []
    for pr in prs:
        if remedy_issues(pr):
            continue
        out.append({
            "where": f"#{pr['number']}",
            "title": pr.get("title") or "",
            "detail": "carries `do-not-merge` with no resolving issue — a passing mention of an issue is not a "
                      "remedy. Name it as one (`resolves #NNN`, `blocked by #NNN`, `until #NNN`) in a comment, "
                      "or remove the tag (issue #948)",
        })
    return out


def report(prs: list[dict], held: list[dict]) -> str:
    lines = [f"[check-holds] {len(prs)} PR(s) carry `{LABEL}` · {len(held)} without a resolving issue"]
    for pr in prs:
        numbers = remedy_issues(pr)
        state = ", ".join(f"#{n}" for n in numbers) if numbers else "NO REMEDY"
        lines.append(f"  #{pr['number']}: {state} — {pr.get('title') or ''}"[:160])
    for item in held:
        lines.append(f"[check-holds] FAIL {item['where']}: {item['detail']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "check holds").splitlines()[0])
    parser.add_argument("mode", nargs="?", default="check", choices=("check", "report"))
    parser.add_argument("--repo", default="asimov-agent/llgenie")
    parser.add_argument("--fixture", default=None,
                        help="read PRs from a JSON file instead of the API (the tests use this)")
    args = parser.parse_args(argv)

    if args.fixture:
        prs = json.loads(Path(args.fixture).read_text(encoding="utf-8"))
    else:
        prs = held_prs(args.repo)

    held = findings(prs)
    print(report(prs, held))
    if args.mode == "report":
        return 0
    return 1 if held else 0


if __name__ == "__main__":
    sys.exit(main())
