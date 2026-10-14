"""The issue-implementer's deterministic dispatcher (issue #248).

Scope: there is no bot that **implements an issue** — a red PR gets repaired
(#222), open PRs get kept rebased (#246), the container is specified (#238) —
but the first PR is still written by hand. This is the unit-testable core: pick
exactly ONE issue, at most 3 per UTC day, one at a time, each left as a
draft-free reviewable PR that is **never merged**. The LLM step (Hermes reading
`issue.md` + AGENTS.md and implementing) is `make implement-issue` in the
workflow; this dispatcher only decides *what* to implement and opens the PR.

Commands (stdlib only, no LLM):
  count                  PRs the bot already opened today (the cap numerator)
  dispatch [--dry]       cap -> pick one issue -> claim -> write issue.md + branch
  open-pr                open a draft-free PR linking the issue (never merges)

The GitHub API is reached ONLY through a `gh` on PATH (or `--gh`): every test
asserts the exact argv the product builds by pointing this at a fake `gh`, the
same shape `tests/test_engine_skill_gap.py` uses for its spawn.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Author the PRs count as from the bot; a human's work is never counted toward the cap.
BOT_AUTHOR = "github-actions[bot]"
MAX_PER_DAY = 3
SLUG_LEN = 40


def _gh(gh: str, args: list[str]) -> str:
    r = subprocess.run([gh, *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"[issue-implementer] {gh} {' '.join(args)} failed ({r.returncode}): {r.stderr.strip()}")
    return r.stdout


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def count(gh: str, repo: str, bot: str, today: str | None = None) -> int:
    """PRs the bot already opened in the current UTC day — the cap numerator, from GitHub."""
    d = today or _today()
    out = _gh(gh, ["search", "prs", "--repo", repo, "--author", bot,
                   "--created", f">={d} 00:00Z", "--json", "number", "--limit", "100"])
    items = json.loads(out or "[]")
    return len(items or [])


def _slug(title: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return s[:SLUG_LEN].rstrip("-") or "issue"


def _issue_list(gh: str, repo: str, label: str) -> list[dict]:
    out = _gh(gh, ["issue", "list", "--repo", repo, "--state", "open", "--label", label,
                   "--limit", "100", "--json", "number,title,createdAt"])
    return json.loads(out or "[]")


def dispatch(gh: str, repo: str, bot: str, dry: bool = False, today: str | None = None,
             out_path: Path = Path("issue.md"), force_issue: int | None = None) -> dict:
    """Apply the cap, pick ONE issue, claim it, and emit the branch + issue.md."""
    d = today or _today()
    n = count(gh, repo, bot, d)
    if n >= MAX_PER_DAY:
        print(f"[issue-implementer] cap reached: {n}/{MAX_PER_DAY} today, next issue tomorrow")
        return {"action": "cap", "count": n, "issue": None}

    if force_issue is not None:
        # A workflow_dispatch pins dispatch to the explicit issue (owner-only path).
        detail = json.loads(_gh(gh, ["issue", "view", str(force_issue), "--repo", repo,
                                     "--json", "number,title,body,state"]))
        if detail.get("state") != "open":
            print(f"[issue-implementer] forced issue #{force_issue} is '{detail.get('state')}', not open")
            return {"action": "none", "count": n, "issue": None}
        title = detail["title"]
        num = detail["number"]
    else:
        # Labeled `agent:implement` first (oldest label first); else the oldest `agent:ready`.
        labeled = _issue_list(gh, repo, "agent:implement")
        if labeled:
            labeled.sort(key=lambda i: i.get("createdAt") or "")
            issue = labeled[0]
        else:
            ready = _issue_list(gh, repo, "agent:ready")
            if not ready:
                print("[issue-implementer] no issue labelled agent:implement or agent:ready to implement")
                return {"action": "none", "count": n, "issue": None}
            ready.sort(key=lambda i: i.get("createdAt") or "")
            issue = ready[0]
        num = issue["number"]
        title = issue["title"]
        detail = json.loads(_gh(gh, ["issue", "view", str(num), "--repo", repo,
                                     "--json", "number,title,body"]))

    branch = f"agent/issue-{num}-{_slug(title)}"
    body = detail.get("body") or ""
    out_path.write_text(f"# {title}\n\n{body}\n")

    if not dry:
        marker = (f"issue-implementer: claiming #{num} (branch `{branch}`) at "
                  f"{datetime.now(timezone.utc).isoformat(timespec='seconds')} — one issue "
                  f"per run, at most {MAX_PER_DAY}/day, PR left for review (never merged).")
        _gh(gh, ["issue", "comment", str(num), "--repo", repo, "--body", marker])

    print(f"[issue-implementer] picked #{num}: {title} -> {branch} (daily count {n}/{MAX_PER_DAY})")
    return {"action": "dispatch", "count": n, "issue": num, "title": title, "branch": branch}


def open_pr(gh: str, repo: str, num: int, branch: str, title: str, body: str,
            wants: str, dry: bool = False) -> str:
    """Open a draft-free PR linking the issue. Never merges; reports the URL."""
    pr_title = f"{title} (implements #{num})"
    if dry:
        print(f"[issue-implementer] would open #implements{num} from {branch} -> main")
        return ""
    out = _gh(gh, ["pr", "create", "--repo", repo, "--base", "main", "--head", branch,
                   "--title", pr_title, "--body", f"{body}\n\ncloses #{num}\n{wants}"])
    url = out.strip().splitlines()[-1] if out.strip() else ""
    print(f"[issue-implementer] opened {url}")
    return url


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="issue_implementer")
    sub = p.add_subparsers(dest="cmd")

    c = sub.add_parser("count")
    c.add_argument("--gh", default="gh")
    c.add_argument("--repo", required=True)
    c.add_argument("--bot", default=BOT_AUTHOR)
    c.add_argument("--today", default=None)

    d = sub.add_parser("dispatch")
    d.add_argument("--gh", default="gh")
    d.add_argument("--repo", required=True)
    d.add_argument("--bot", default=BOT_AUTHOR)
    d.add_argument("--today", default=None)
    d.add_argument("--dry", action="store_true")
    d.add_argument("--out", default="issue.md")
    d.add_argument("--force-issue", type=int, default=None)

    o = sub.add_parser("open-pr")
    o.add_argument("--gh", default="gh")
    o.add_argument("--repo", required=True)
    o.add_argument("--issue", type=int, required=True)
    o.add_argument("--branch", required=True)
    o.add_argument("--title", default="issue-bot implementation")
    o.add_argument("--body", default="")
    o.add_argument("--wants", default="Verification notes land on the PR as CI runs it.")
    o.add_argument("--dry", action="store_true")

    args = p.parse_args(argv)
    if args.cmd == "count":
        print(count(args.gh, args.repo, args.bot, args.today))
    elif args.cmd == "dispatch":
        res = dispatch(args.gh, args.repo, args.bot, args.dry, args.today,
                       Path(args.out), force_issue=args.force_issue)
        # Machine-readable lines the workflow parses after the human log line.
        print(f"action={res.get('action')}")
        if res.get("issue"):
            print(f"issue={res['issue']}")
            print(f"branch={res['branch']}")
    elif args.cmd == "open-pr":
        url = open_pr(args.gh, args.repo, args.issue, args.branch, args.title, args.body,
                      args.wants, args.dry)
        print(f"pr_url={url}")
    else:
        p.error("need a command: count | dispatch | open-pr")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
