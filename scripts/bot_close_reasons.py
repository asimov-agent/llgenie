#!/usr/bin/env python3
"""Which closed issues did the lane close `not_planned` while a MERGED PR implements them (issue #2869)?

The issue-bot lane files every close it applies with `state_reason: not planned`; the other close
reason, `completed`, is GitHub closing an issue through a merged pull request's closing reference.
When the two reach the same issue, the later one wins in the code but the earlier one can stay in
the record: issue #2048 was closed `not planned` while PR #2863 — the PR whose body closes #2048 —
was still OPEN and mid-landing (issue #2869). This read makes that contradiction countable:

* every MERGED pull request's closing references (`closing_references`, `issue_line_claims`,
  `subject_claims` — the SAME readings `check_pr_closing.py` holds a PR body to) name their target
  issues;
* every targeted issue that is CLOSED and was closed by the lane — an `agent:closed` label or a
  closed-timeline event performed by the bot account — becomes a row;
* a row whose `state_reason` is `not_planned` while a merged PR implements it is FLAGGED as
  contradicting its own close evidence.

The read prints COUNTS and issue numbers, never payload bodies. A stream it cannot read exits
non-zero: a read that fails must never look like a clean sweep.

Commands:
    bot_close_reasons.py report --repo <owner/repo> [--gh gh] [--bot <login>[,<login>]]
                                 [--pages N] [--max-issues N]

Usage:
    make bot-close-reasons-report REPO=<owner/repo>
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys

# The gate that reds an unbound or misbound closing reference is the ONE closing grammar this repo
# holds PRs to; this read maps merged PRs onto issues through the same seam so the two cannot
# disagree about which issue a merged PR closes (issue #2869).
from check_pr_closing import closing_references, issue_line_claims, subject_claims

#: The lane's own close label (issue_bot_gates vocabulary): its presence says the lane closed it.
LANE_CLOSE_LABEL = "agent:closed"


def _gh_json(gh: str, path: str) -> object:
    """One `gh api` read as JSON; a failed or unreadable read is a hard exit, never an empty sweep."""
    r = subprocess.run([gh, "api", path], capture_output=True, text=True)  # proc-allow: direct subprocess call site, tracked remainder for issue #797 (migrate onto scripts/proc.py in a per-module batch)
    if r.returncode != 0:
        raise SystemExit(f"[bot-close-reasons] cannot read {path}: gh rc={r.returncode} "
                         f"({(r.stderr or '').strip()[:200]})")
    try:
        return json.loads(r.stdout or "null")
    except json.JSONDecodeError:
        raise SystemExit(f"[bot-close-reasons] cannot read {path}: the response is not JSON")


def merged_pulls(gh: str, repo: str, pages: int) -> list[dict]:
    """Merged pull requests, newest-updated first, until the pages run out or the cap is reached."""
    out: list[dict] = []
    for page in range(1, pages + 1):
        rows = _gh_json(gh, f"repos/{repo}/pulls?state=closed&per_page=100&sort=updated"
                            f"&direction=desc&page={page}")
        if not isinstance(rows, list) or not rows:
            break
        out += [p for p in rows if isinstance(p, dict) and p.get("merged_at")]
        if len(rows) < 100:
            break
    return out


def claimed_issues(pulls: list[dict]) -> dict[int, list[dict]]:
    """issue number -> the merged PRs whose title/body make a closing claim on it (gate grammar)."""
    targets: dict[int, list[dict]] = {}
    for p in pulls:
        title = p.get("title") or ""
        text = f"{title}\n{p.get('body') or ''}"
        nums = {int(n) for n in closing_references(text)}
        nums |= {int(n) for n in issue_line_claims(text)}
        nums |= {int(n) for n in subject_claims(title)}
        for n in nums:
            targets.setdefault(n, []).append(p)
    return targets


def closed_by(gh: str, repo: str, num: int, bots: tuple[str, ...]) -> str | None:
    """How the lane closed this issue: its `agent:closed` label, or a closed event by a bot account."""
    timeline = _gh_json(gh, f"repos/{repo}/issues/{num}/timeline?per_page=100")
    if not isinstance(timeline, list):
        return None
    for e in timeline:
        if not isinstance(e, dict) or e.get("event") != "closed":
            continue
        actor = (e.get("actor") or {}).get("login") \
            or (e.get("performed_by") or {}).get("login") or ""
        if actor in bots:
            return f"closed-by:{actor}"
    return None


def report(repo: str, gh: str = "gh", bot: str = "github-actions[bot]",
           pages: int = 10, max_issues: int = 200) -> int:
    """Print every lane-closed issue a merged PR's closing reference targets, with its reason."""
    bots = tuple(b.strip() for b in bot.split(",") if b.strip())
    pulls = merged_pulls(gh, repo, pages)
    targets = claimed_issues(pulls)
    rows: list[dict] = []
    read_budget = max_issues
    for num in sorted(targets, reverse=True):
        if read_budget <= 0:
            break  # the cap is a READ budget over claimed issues, newest-number first
        read_budget -= 1
        issue = _gh_json(gh, f"repos/{repo}/issues/{num}")
        if not isinstance(issue, dict) or issue.get("pull_request") is not None:
            continue  # a shared-sequence number that is itself a PR is not an issue row
        if (issue.get("state") or "") != "closed":
            continue  # the claim has not landed as a close yet: not this read's subject
        labels = {str(l.get("name")) for l in issue.get("labels") or [] if isinstance(l, dict)}
        closer = LANE_CLOSE_LABEL if LANE_CLOSE_LABEL in labels else closed_by(gh, repo, num, bots)
        if closer is None:
            continue  # closed by someone else entirely: not the lane's record to audit
        rows.append({"number": num, "state_reason": issue.get("state_reason") or "",
                     "closer": closer, "prs": targets[num]})
    flagged = [r for r in rows if r["state_reason"] == "not_planned"]
    print(f"bot_close_reasons: repo={repo} merged_prs_read={len(pulls)} "
          f"issues_claimed={len(targets)} bot_closed_rows={len(rows)} flagged={len(flagged)}")
    for r in rows:
        prs = ", ".join(f"#{p.get('number')}" for p in r["prs"])
        print(f"  #{r['number']} state_reason={r['state_reason'] or 'unknown'} closer={r['closer']} "
              f"merged_prs={prs}")
        if r["state_reason"] == "not_planned":
            print(f"    FLAG: merged {prs} carries a closing reference to #{r['number']} while the "
                  "issue is filed `not_planned` — the closure contradicts its own close evidence")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="bot_close_reasons.py")
    sub = p.add_subparsers(dest="cmd")
    r = sub.add_parser("report")
    r.add_argument("--repo", required=True)
    r.add_argument("--gh", default="gh")
    r.add_argument("--bot", default="github-actions[bot]",
                   help="comma-separated logins whose closes count as the lane's own")
    r.add_argument("--pages", type=int, default=10, help="pages of closed PRs to read (100 each)")
    r.add_argument("--max-issues", type=int, default=200,
                   help="read budget over claimed issues, newest-number first")
    args = p.parse_args(argv)
    if args.cmd != "report":
        p.print_help()
        return 2
    return report(args.repo, args.gh, args.bot, args.pages, args.max_issues)


if __name__ == "__main__":
    sys.exit(main())
