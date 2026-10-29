#!/usr/bin/env python3
"""A bot review VERDICT is a comment with a machine-readable mark, never an approval (issue #852).

Every bot pushes with the owner's token, so the PR author is the owner account and GitHub refuses
`gh pr review --approve` with "Can not approve your own pull request". `reviewDecision` therefore can
never leave `REVIEW_REQUIRED` on a bot-authored PR, and a complete reviewer verdict that only lives as
prose in the thread is invisible to `scripts/auto_merge.py::decide()` — a green PR sits `BLOCKED`
forever, or until a human clicks approve.

The mark is this comment, with the head it reviewed written INTO it:

    <!-- bot-verdict: head=<40-hex sha> verdict=approve reviewer=<login> -->

`auto_merge` accepts "reviewed by a bot verdict at head <sha>" only when that `<sha>` equals the PR's
CURRENT `headRefOid`: a verdict describes one tree, and a verdict on an older commit says nothing about
the commit that would merge (`verdict_for_head`). The marker is deliberately not a GitHub approval and
not a label: it cannot flip `reviewDecision`, it cannot be mistaken for a human sign-off, and it needs no
second identity.

Trust is bounded twice, because a PR comment can be written by anyone:

  * the comment's AUTHOR must be one of the repository's own identities (`TRUSTED_VERDICT_AUTHORS`) or a
    bot login (`…[bot]`);
  * the `reviewer=` named in the marker must equal that comment's author, so a stranger cannot write
    `reviewer=github-actions[bot]` and borrow the bot's name.

Commands (stdlib only, the GitHub API only through a `gh` on PATH):
  bot_verdict post --repo R --pr N --head SHA --verdict approve|changes [--reviewer L] [--note TEXT]
  bot_verdict show --repo R --pr N [--head SHA]        print the verdict the merge gate would read
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

#: The identities this repository allows on a PR (AGENTS.md: `Andy Holst`, `Asimov Agent`), as logins.
#: `scripts/auto_merge.py` names the same two for authorship; `tests/test_bot_verdict.py` compares the
#: sets so the two cannot drift.
TRUSTED_VERDICT_AUTHORS = ("andyholst", "asimov-agent")
#: A workflow's own token acts as `github-actions[bot]` (an App login, never a collaborator), and any
#: `…[bot]` login is a bot too.
BOT_LOGINS = ("github-actions[bot]", "app/github-actions")
#: The one verdict that clears a review block.
ACCEPTING = ("approve", "approved", "pass", "lgtm")
#: A verdict that asks for work: it blocks the merge at the head it names, and it is never an approval.
BLOCKING = ("changes", "change-requested", "request-changes", "reject")
#: The marker. `head` is the FULL sha the verdict reviewed, which is what makes a stale verdict stale.
MARKER_RE = re.compile(
    r"<!--\s*bot-verdict:\s*head=(?P<head>[0-9a-fA-F]{7,40})\s+verdict=(?P<verdict>[a-z-]+)"
    r"\s+reviewer=(?P<reviewer>[^\s>]+)\s*-->")


def marker(head: str, verdict: str, reviewer: str) -> str:
    """The machine-readable mark, exactly the shape `parse` reads back."""
    return f"<!-- bot-verdict: head={(head or '').strip()} verdict={(verdict or '').strip().lower()} " \
           f"reviewer={(reviewer or '').strip()} -->"


def parse(body: str) -> "dict | None":
    """The FIRST verdict marker in a comment body, or None.

    One comment carries one verdict: a producer that wants to change its mind posts a second one, which
    is newer and therefore wins (`verdict_for_head`), and the earlier one stays readable as history.
    """
    m = MARKER_RE.search(body or "")
    if not m:
        return None
    return {"head": m.group("head").lower(), "verdict": m.group("verdict").lower(),
            "reviewer": m.group("reviewer")}


def trusted(login: str) -> bool:
    who = (login or "").strip()
    return who.lower() in [a.lower() for a in TRUSTED_VERDICT_AUTHORS] or \
        who.lower() in BOT_LOGINS or who.lower().endswith("[bot]")


def verdict_for_head(comments: "list[dict] | None", head: str) -> "dict | None":
    """The NEWEST trusted verdict whose marker names exactly `head`, or None.

    `comments` is `gh pr view --json comments`' list (`{author: {login}, body, …}`). A marker for any
    other sha — an older commit, a superseded push — is not a verdict about this head, and is skipped:
    the whole point is that a stale verdict must not count (#852).
    """
    want = (head or "").strip().lower()
    if not want:
        return None
    found = None
    for c in comments or []:
        v = parse(str((c or {}).get("body") or ""))
        if not v:
            continue
        author = (((c or {}).get("author") or {}).get("login") or "").strip()
        if not trusted(author):
            continue
        # No impersonation: the name in the marker must be the account that wrote the comment.
        if v["reviewer"].lower() != author.lower():
            continue
        if v["head"] != want:
            continue
        found = dict(v, author=author)      # the last one in thread order wins
    return found


def _gh(gh: str, args: "list[str]", token: str = "") -> str:
    env = None
    if token:
        env = {**os.environ, "GH_TOKEN": token}
    r = subprocess.run([gh, *args], capture_output=True, text=True, env=env)
    if r.returncode != 0:
        raise SystemExit(f"[bot-verdict] {gh} {' '.join(args)} failed ({r.returncode}): {r.stderr.strip()}")
    return r.stdout


def comments(gh: str, repo: str, pr: int) -> list[dict]:
    out = _gh(gh, ["pr", "view", str(pr), "--repo", repo, "--json", "comments"])
    return json.loads(out or "{}").get("comments") or []


def body(head: str, verdict: str, reviewer: str, note: str = "") -> str:
    what = {"approve": "approve", "approved": "approve", "pass": "approve", "lgtm": "approve"}.get(
        verdict.lower(), "request changes" if verdict.lower() in BLOCKING else verdict.lower())
    text = (f"{marker(head, verdict, reviewer)}\n\n"
            f"**Bot review verdict: {what}** at head `{(head or '')[:12]}` (reviewer `{reviewer}`).\n")
    if (note or "").strip():
        text += f"\n{(note or '').strip()}\n"
    text += ("\nThis is a verdict comment, never a GitHub approval: a bot pushes with the owner's token, "
             "so GitHub refuses its own approval of the PR. `scripts/auto_merge.py` reads this mark only "
             "when the head above is still the PR's current head — a verdict on an older commit does not "
             "count (`docs/BOTS.md`).")
    return text


def post(gh: str, repo: str, pr: int, head: str, verdict: str, reviewer: str,
         note: str = "", dry: bool = False) -> int:
    """Post ONE verdict comment per (head, verdict); re-posting the same one is a no-op."""
    head = (head or "").strip().lower()
    verdict = (verdict or "").strip().lower()
    if len(head) != 40 or not re.fullmatch(r"[0-9a-f]{40}", head):
        print(f"[bot-verdict] refusing: --head must be the FULL 40-hex commit sha, got {head!r} "
              f"(a short sha would make a stale verdict look current)", file=sys.stderr)
        return 2
    if verdict not in ACCEPTING + BLOCKING:
        print(f"[bot-verdict] refusing: --verdict must be one of {', '.join(ACCEPTING + BLOCKING)}",
              file=sys.stderr)
        return 2
    existing = [c for c in comments(gh, repo, pr) if parse(str(c.get("body") or ""))]
    for c in existing:
        v = parse(str(c.get("body") or ""))
        author = (((c.get("author") or {}).get("login")) or "")
        if v["head"] == head and v["verdict"] == verdict and author.lower() == reviewer.lower():
            print(f"[bot-verdict] PR #{pr} already carries {verdict} at {head[:8]} from `{reviewer}`")
            return 0
    if dry:
        print(f"[bot-verdict] would post {verdict} at {head[:8]} on PR #{pr} as `{reviewer}`")
        return 0
    _gh(gh, ["pr", "comment", str(pr), "--repo", repo, "--body", body(head, verdict, reviewer, note)])
    print(f"[bot-verdict] posted {verdict} at {head[:8]} on PR #{pr} as `{reviewer}`")
    return 0


def show(gh: str, repo: str, pr: int, head: str = "") -> int:
    """Print the verdict the merge gate would read for `head` (default: the PR's current head)."""
    if not head:
        out = _gh(gh, ["pr", "view", str(pr), "--repo", repo, "--json", "headRefOid"])
        head = (json.loads(out or "{}").get("headRefOid") or "")
    v = verdict_for_head(comments(gh, repo, pr), head)
    print(f"[bot-verdict] PR #{pr} at {(head or '?')[:8]}: "
          f"{json.dumps(v) if v else 'no trusted verdict for this head'}")
    return 0


def main(argv: "list[str] | None" = None) -> int:
    p = argparse.ArgumentParser(prog="bot_verdict", description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("post", help="post a bot review verdict at one head (deduped per head+verdict)")
    w.add_argument("--repo", required=True)
    w.add_argument("--pr", type=int, required=True)
    w.add_argument("--head", required=True, help="the FULL 40-hex commit sha this verdict reviewed")
    w.add_argument("--verdict", required=True, help="approve | changes")
    w.add_argument("--reviewer", default="", help="the login posting it (default: the token's account)")
    w.add_argument("--note", default="", help="the reviewer's one-paragraph reasoning")
    w.add_argument("--gh", default="gh")
    w.add_argument("--dry", action="store_true")
    s = sub.add_parser("show", help="print the verdict the merge gate would read")
    s.add_argument("--repo", required=True)
    s.add_argument("--pr", type=int, required=True)
    s.add_argument("--head", default="", help="default: the PR's current headRefOid")
    s.add_argument("--gh", default="gh")

    args = p.parse_args(argv)
    if args.cmd == "show":
        return show(args.gh, args.repo, args.pr, args.head)
    reviewer = (args.reviewer or "").strip()
    if not reviewer:
        reviewer = (os.environ.get("BOT_VERDICT_REVIEWER") or "").strip()
    if not reviewer:
        print("[bot-verdict] refusing: no --reviewer and BOT_VERDICT_REVIEWER is empty — the marker must "
              "name the account that posts it", file=sys.stderr)
        return 2
    return post(args.gh, args.repo, args.pr, args.head, args.verdict, reviewer, args.note, args.dry)


if __name__ == "__main__":
    raise SystemExit(main())
