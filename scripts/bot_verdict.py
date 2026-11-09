#!/usr/bin/env python3
"""A bot review VERDICT is a comment with a machine-readable mark, never an approval (issue #852).

Every bot pushes with the owner's token, so the PR author is the owner account and GitHub refuses
`gh pr review --approve` with "Can not approve your own pull request". `reviewDecision` therefore can
never leave `REVIEW_REQUIRED` on a bot-authored PR, and a complete reviewer verdict that only lives as
prose in the thread is invisible to `scripts/auto_merge.py::decide()` — a green PR sits `BLOCKED`
forever, or until a human clicks approve.

The mark is this comment, with the head it reviewed written INTO it, and the run that measured that head:

    <!-- bot-verdict: head=<40-hex sha> run=<run id> verdict=approve reviewer=<login> -->

`auto_merge` accepts "reviewed by a bot verdict at head <sha>" only when that `<sha>` equals the PR's
CURRENT `headRefOid`: a verdict describes one tree, and a verdict on an older commit says nothing about
the commit that would merge (`verdict_for_head`). The `run=` id is the record of WHICH run measured that
tree — a verdict that names only a sha cannot be audited, because two heads could carry a marker with the
same sha and no record of what was measured (#1551). The marker is deliberately not a GitHub approval and
not a label: it cannot flip `reviewDecision`, it cannot be mistaken for a human sign-off, and it needs no
second identity.

Trust is bounded by who may post AND who the marker names, because a PR comment can be written by
anyone:

  * the comment's AUTHOR must be one of the repository's own identities (`TRUSTED_VERDICT_AUTHORS`) or a
    bot login (`…[bot]`); and
  * APPROVER != MERGER (issue #2244): an ACCEPTING verdict whose `reviewer=` names a merge-path identity
    — the owner PAT that merges (`asimov-agent`) or the job/APPROVER token (`github-actions[bot]`) — is
    the merger approving its own gate evidence, never an independent review. It is rejected whatever
    the comment's author. A BLOCKING verdict from any trusted reviewer still holds the PR (asking for
    work is always the safe direction); and
  * no-impersonation: when the marker is posted directly (author != `github-actions[bot]`), `reviewer=`
    MUST equal that comment's author, so a stranger cannot write `reviewer=andyholst` and borrow a
    trusted name; when the marker is authored by the review-verdict workflow token (`github-actions[bot]`,
    a trusted relay), `reviewer=` is the REAL review event's author and must be a distinct identity
    allowed to review (`allowed_reviewer`).

Commands (stdlib only, the GitHub API only through a `gh` on PATH):
  bot_verdict post --repo R --pr N --head SHA --run RUN --verdict approve|changes [--reviewer L] [--note TEXT]
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
#: The merge-path identities (issue #2244, the #1088 class): the tokens the repo's OWN auto-merge uses
#: to clear a review block — the owner PAT that merges (`BUMP_TOKEN` -> `asimov-agent`) and the job /
#: APPROVER token (`github.token` -> `github-actions[bot]`, the same App login as `app/github-actions`).
#: An ACCEPTING verdict whose `reviewer=` names one of these is the merger approving its own gate
#: evidence, so it is never evidence of an independent review (approver != merger). A BLOCKING verdict
#: from one still holds the PR: asking for work is always the safe direction, and the reviewer lane
#: runs under these same public identities for its `changes` verdicts.
MERGER_LOGINS = tuple(a.lower() for a in ("asimov-agent", "github-actions[bot]", "app/github-actions"))
#: The one verdict that clears a review block.
ACCEPTING = ("approve", "approved", "pass", "lgtm")
#: A verdict that asks for work: it blocks the merge at the head it names, and it is never an approval.
BLOCKING = ("changes", "change-requested", "request-changes", "reject")
#: The marker. `head` is the FULL sha the verdict reviewed, which is what makes a stale verdict stale,
#: and `run` is the Actions run id that measured that head (#1551) — a verdict with no run cannot be
#: audited (two heads could carry a marker for the same sha), so the slot is REQUIRED in the shape.
MARKER_RE = re.compile(
    r"<!--\s*bot-verdict:\s*head=(?P<head>[0-9a-fA-F]{7,40})\s+run=(?P<run>\d+)\s+"
    r"verdict=(?P<verdict>[a-z-]+)\s+reviewer=(?P<reviewer>[^\s>]+)\s*-->")


def marker(head: str, run: str, verdict: str, reviewer: str) -> str:
    """The machine-readable mark, exactly the shape `parse` reads back."""
    return f"<!-- bot-verdict: head={(head or '').strip()} run={(run or '').strip()} " \
           f"verdict={(verdict or '').strip().lower()} reviewer={(reviewer or '').strip()} -->"


def parse(body: str) -> "dict | None":
    """The FIRST verdict marker in a comment body, or None.

    One comment carries one verdict: a producer that wants to change its mind posts a second one, which
    is newer and therefore wins (`verdict_for_head`), and the earlier one stays readable as history.
    """
    m = MARKER_RE.search(body or "")
    if not m:
        return None
    return {"head": m.group("head").lower(), "run": m.group("run"),
            "verdict": m.group("verdict").lower(), "reviewer": m.group("reviewer")}


def trusted(login: str) -> bool:
    who = (login or "").strip()
    return who.lower() in [a.lower() for a in TRUSTED_VERDICT_AUTHORS] or \
        who.lower() in BOT_LOGINS or who.lower().endswith("[bot]")


def allowed_reviewer(login: str) -> bool:
    """A login that may be named as an INDEPENDENT reviewer (issue #2244, approver != merger).

    A repo identity or a bot login (`trusted`) that is NOT a merge-path identity: an ACCEPTING verdict
    must come from a genuinely distinct reviewer, never the account whose token would merge the PR.
    `andyholst` is the repo's human reviewer identity; a dedicated reviewer `…[bot]` counts; a
    `changes` verdict does not demand a distinct reviewer (it holds, it never proves).
    """
    who = (login or "").strip()
    return bool(who) and trusted(who) and who.lower() not in MERGER_LOGINS


def verdict_for_head(comments: "list[dict] | None", head: str) -> "dict | None":
    """The NEWEST trusted verdict whose marker names exactly `head`, or None.

    `comments` is `gh pr view --json comments`' list (`{author: {login}, body, …}`). A marker for any
    other sha — an older commit, a superseded push — is not a verdict about this head, and is skipped:
    the whole point is that a stale verdict must not count (#852).
    """
    want = (head or "").strip().lower()
    if not want:
        return None
    accepting = {a.lower() for a in ACCEPTING}
    found = None
    for c in comments or []:
        v = parse(str((c or {}).get("body") or ""))
        if not v:
            continue
        author = (((c or {}).get("author") or {}).get("login") or "").strip()
        if not trusted(author):
            continue
        reviewer = (v.get("reviewer") or "").strip()
        # No impersonation / complementary APPROVER != MERGER (issue #2244): an ACCEPTING verdict
        # whose named reviewer is a merge-path identity is the merger approving its own gate evidence
        # — never an independent review — so it is dropped whatever the comment's author.
        if v.get("verdict", "").lower() in accepting and reviewer.lower() in MERGER_LOGINS:
            continue
        if author.lower() in BOT_LOGINS:
            # The review-verdict workflow token (`github-actions[bot]`) authors a marker whose
            # `reviewer=` is the TRUE review event's author and may differ from the bot itself; that
            # reviewer must still be a distinct identity allowed to review (approver != merger).
            if not allowed_reviewer(reviewer):
                continue
        else:
            # A direct post (the reviewer lane writing `make bot-verdict`) must name its own author:
            # a stranger cannot write `reviewer=<trusted name>` and borrow it (#852).
            if reviewer.lower() != author.lower():
                continue
        if v["head"] != want:
            continue
        found = dict(v, author=author)      # the last one in thread order wins
    return found


def _gh(gh: str, args: "list[str]", token: str = "") -> str:
    env = None
    if token:
        env = {**os.environ, "GH_TOKEN": token}
    r = subprocess.run([gh, *args], capture_output=True, text=True, env=env)  # proc-allow: direct subprocess call site, tracked remainder for issue #797 (migrate onto scripts/proc.py in a per-module batch)
    if r.returncode != 0:
        raise SystemExit(f"[bot-verdict] {gh} {' '.join(args)} failed ({r.returncode}): {r.stderr.strip()}")
    return r.stdout


def _runs_for_head(gh: str, repo: str, head: str, conclusion: str = "") -> list[dict]:
    """The pull_request Action runs at `head` (the #1551 read, shared with auto_merge).

    `conclusion` optionally filters server-side (`conclusion=success`); the caller still re-checks the
    pitfall fields (status/conclusion/id) client-side, because a server filter is not a guarantee.
    Raises SystemExit when the read fails (the caller turns that into a refusal, never a silent pass).
    """
    query = f"head_sha={head}&event=pull_request&per_page=100"
    if conclusion:
        query += f"&conclusion={conclusion}"
    out = _gh(gh, ["api", f"repos/{repo}/actions/runs?{query}",
                   "--jq", "[.workflow_runs[] | {status: .status, conclusion: .conclusion, id: .id}]"])
    runs = json.loads(out or "[]")
    return runs if isinstance(runs, list) else []


def _not_concluded_success_at_head(gh: str, repo: str, head: str, run: str) -> str:
    """A reason when `run` is NOT a concluded-success pull_request run at `head`, else \"\"."""
    try:
        runs = _runs_for_head(gh, repo, head)
    except SystemExit as exc:
        return f"could not read head {head[:8]}'s runs to verify run {run} ({exc})"
    ids = {str(r.get("id") or "") for r in runs}
    if run not in ids:
        return (f"run {run} is not a pull_request run at head {head[:8]} (runs there: "
                f"{', '.join(sorted(ids)) or 'none'})")
    for r in runs:
        if str(r.get("id") or "") != run:
            continue
        if str(r.get("status") or "").lower() != "completed":
            return f"run {run} has not concluded at head {head[:8]}, so it never proved that tree green"
        if str(r.get("conclusion") or "").lower() != "success":
            return (f"run {run} concluded {r.get('conclusion') or 'none'} at head {head[:8]} — an "
                    f"approve verdict's run= must be a concluded-SUCCESS run, never a red one (#2035)")
    return ""


def comments(gh: str, repo: str, pr: int) -> list[dict]:
    out = _gh(gh, ["pr", "view", str(pr), "--repo", repo, "--json", "comments"])
    return json.loads(out or "{}").get("comments") or []


def body(head: str, run: str, verdict: str, reviewer: str, note: str = "") -> str:
    what = {"approve": "approve", "approved": "approve", "pass": "approve", "lgtm": "approve"}.get(
        verdict.lower(), "request changes" if verdict.lower() in BLOCKING else verdict.lower())
    text = (f"{marker(head, run, verdict, reviewer)}\n\n"
            f"**Bot review verdict: {what}** at head `{(head or '')[:12]}` (run `{run or '?'}`, "
            f"reviewer `{reviewer}`).\n")
    if (note or "").strip():
        text += f"\n{(note or '').strip()}\n"
    text += ("\nThis is a verdict comment, never a GitHub approval: a bot pushes with the owner's token, "
             "so GitHub refuses its own approval of the PR. `scripts/auto_merge.py` reads this mark only "
             "when the head above is still the PR's current head — a verdict on an older commit does not "
             "count (`docs/BOTS.md`).")
    return text


def post(gh: str, repo: str, pr: int, head: str, run: str, verdict: str, reviewer: str,
         note: str = "", dry: bool = False) -> int:
    """Post ONE verdict comment per (head, verdict); re-posting the same one is a no-op."""
    head = (head or "").strip().lower()
    run = (run or "").strip()
    verdict = (verdict or "").strip().lower()
    if len(head) != 40 or not re.fullmatch(r"[0-9a-f]{40}", head):
        print(f"[bot-verdict] refusing: --head must be the FULL 40-hex commit sha, got {head!r} "
              f"(a short sha would make a stale verdict look current)", file=sys.stderr)
        return 2
    if not re.fullmatch(r"\d+", run):
        print(f"[bot-verdict] refusing: --run must be the Actions run id that measured this head, got "
              f"{run!r} (a verdict with no run cannot be audited — #1551)", file=sys.stderr)
        return 2
    if verdict not in ACCEPTING + BLOCKING:
        print(f"[bot-verdict] refusing: --verdict must be one of {', '.join(ACCEPTING + BLOCKING)}",
              file=sys.stderr)
        return 2
    # #2035: an ACCEPTING verdict's `run=` is the record of WHICH run proved that tree green, so the
    # slot must name a real concluded-SUCCESS run at `--head`, never a red/cancelled/unfinished sibling
    # at the same head. A `changes` verdict cites the run that named the problem and may cite any run.
    if verdict in ACCEPTING:
        why = _not_concluded_success_at_head(gh, repo, head, run)
        if why:
            print(f"[bot-verdict] refusing: --verdict approve needs --run to be a concluded-SUCCESS "
                  f"run at --head {head[:8]}; {why} (issue #2035)", file=sys.stderr)
            return 2
    existing = [c for c in comments(gh, repo, pr) if parse(str(c.get("body") or ""))]
    for c in existing:
        v = parse(str(c.get("body") or ""))
        # Dedupe on the marker itself (head, run, verdict, reviewer), not the comment author: the
        # review-verdict workflow authors as `github-actions[bot]` while `reviewer=` names the true
        # review author, so author==reviewer is no longer the idempotence key (issue #2244).
        if (v["head"] == head and v["run"] == run and v["verdict"] == verdict
                and v["reviewer"] == reviewer):
            print(f"[bot-verdict] PR #{pr} already carries {verdict} at {head[:8]} "
                  f"(run {run}) from `{reviewer}`")
            return 0
    if dry:
        print(f"[bot-verdict] would post {verdict} at {head[:8]} (run {run}) on PR #{pr} as `{reviewer}`")
        return 0
    _gh(gh, ["pr", "comment", str(pr), "--repo", repo, "--body", body(head, run, verdict, reviewer, note)])
    print(f"[bot-verdict] posted {verdict} at {head[:8]} (run {run}) on PR #{pr} as `{reviewer}`")
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
    w.add_argument("--run", required=True, help="the Actions run id that measured this head (issue #1551)")
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
    return post(args.gh, args.repo, args.pr, args.head, args.run, args.verdict, reviewer, args.note, args.dry)


if __name__ == "__main__":
    raise SystemExit(main())
