"""Which OPEN issue a merged PR already implemented — the linkage the in-repo guard cannot see (#325).

`make check-pr-hygiene` reads the producers the repository owns, so it catches a commit or PR *body*
that is empty or a placeholder. It cannot see what happened at PR time: whether the PR that merged
actually **closed** the issue it implements. Measured on `main`, 13 of 38 merged PRs carried no closing
reference — and when the body carries no `closes #<n>`, GitHub leaves the issue OPEN even though the PR
that implemented it has merged. That is a stale-open issue: the tracker says "not done" about work that
shipped. This module finds exactly those, with the evidence, and closes them.

How a PR is read for the issue it implements — three signals, in the order the merge commit is the
strongest (`gh` resolves the first one for us):

1. `closingIssuesReferences` — the refs GitHub parsed from the body. Non-empty means the issue was
   closed at merge; nothing to clean.
2. the **merge commit message**, whose `Issue: #<n>` line the repo's own hygiene rule requires;
3. the PR **title**'s trailing `(#<n>)`.

A signal that resolves to an issue which is STILL OPEN is a candidate — unless the PR's own body lists
that issue under its `Not covered` section. A remainder is a first-class linked work item per AGENTS.md,
not a missed close, so it is reported as `remainder` and LEFT OPEN. That distinction is the whole
correctness of this bot: #344 named #339-#343 under `Not covered` while implementing #256, so #256 is a
stale-open close and #339-#343 are remainders — and a bot that could not tell them apart would close
work that is still being tracked.

Reads GitHub through `gh`, which the tests stub on `PATH` (the repo's allowance for an external CLI).
`--dry` prints the decision and mutates nothing; `--apply` posts the evidence comment and closes.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bot_claims  # noqa: E402  the shared protocol (issue #279)

#: This bot, as the claim marker names it. One name source for every bot (scripts/bot_claims.py).
CLEANER = bot_claims.CLEANER

#: The repo's own hygiene rule names the implemented issue on the merge commit's first lines.
_ISSUE_IN_COMMIT = re.compile(r"(?im)^\s*Issue:\s*#(\d+)\b")
#: The PR-title convention the repo already uses: `... (#<n>)` at the end.
_ISSUE_IN_TITLE = re.compile(r"\(#(\d+)\)\s*$")
#: A `Not covered` heading — the section whose items are remainders, not missed closes.
_NOT_COVERED = re.compile(r"(?im)^\s*#{0,6}\s*Not covered\b")
_ANY_HEADING = re.compile(r"(?m)^\s*#{1,6}\s+\S")
_ISSUE_NUMBER = re.compile(r"#(\d+)")


def _gh(args: list[str]) -> str:
    """One `gh` call, its stdout. Raises with the real stderr when gh fails."""
    r = subprocess.run(["gh", *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args)} failed: {r.stderr.strip()}")
    return r.stdout


def merged_prs(repo: str, limit: int = 60) -> list[dict]:
    """Recently merged PRs with the fields the decision needs (one API call)."""
    out = _gh(["pr", "list", "--repo", repo, "--state", "merged", "--limit", str(limit),
               "--json", "number,title,body,mergedAt,closingIssuesReferences,mergeCommit"])
    return json.loads(out or "[]")


def open_issues(repo: str) -> list[dict]:
    """Every open issue, with the title the report quotes (paged by gh)."""
    out = _gh(["issue", "list", "--repo", repo, "--state", "open", "--limit", "200",
               "--json", "number,title"])
    return json.loads(out or "[]")


def not_covered(body: str | None) -> set[int]:
    """The issue numbers a PR's `Not covered` section names — its declared remainders.

    The section runs from its heading to the next heading of the same document (or the end), so a
    `Not covered` list cannot swallow an unrelated later section. A PR with no such section declares
    no remainder, and then every issue it names is something it meant to close.
    """
    text = body or ""
    head = _NOT_COVERED.search(text)
    if not head:
        return set()
    rest = text[head.end():]
    nxt = _ANY_HEADING.search(rest)
    section = rest[:nxt.start()] if nxt else rest
    return {int(m) for m in _ISSUE_NUMBER.findall(section)}


def implemented_issue(pr: dict) -> tuple[int, str] | None:
    """(the issue this merged PR implements, how it says so), or None when it names none.

    Order matters: the merge commit is the strongest statement, then the title. A PR whose body's
    `closingIssuesReferences` is non-empty closed its issue at merge and is not this bot's business.
    """
    if pr.get("closingIssuesReferences"):
        return None
    message = ((pr.get("mergeCommit") or {}).get("message") or "")
    m = _ISSUE_IN_COMMIT.search(message)
    if m:
        return int(m.group(1)), "the merge commit's `Issue:` line"
    m = _ISSUE_IN_TITLE.search(pr.get("title") or "")
    if m:
        return int(m.group(1)), "the title's trailing `(#n)`"
    return None


def decide(pr: dict, open_by_number: dict[int, dict]) -> dict | None:
    """What this bot would do about one merged PR: a finding dict, or None when there is nothing.

    Every branch states its reason as plain text so a run's output is auditable without re-asking
    GitHub — a PR that implemented nothing is as interesting as one that implemented a still-open issue.
    """
    found = implemented_issue(pr)
    if found is None:
        return None
    issue_number, evidence = found
    issue = open_by_number.get(issue_number)
    if issue is None:
        return None  # the issue is closed (or never existed): the linkage held
    remainders = not_covered(pr.get("body"))
    if issue_number in remainders:
        return {"action": "remainder", "issue": issue_number, "pr": pr["number"],
                "evidence": evidence, "title": issue.get("title", ""),
                "reason": "named under the PR's `Not covered` — a tracked remainder, left open"}
    return {"action": "close", "issue": issue_number, "pr": pr["number"], "evidence": evidence,
            "title": issue.get("title", ""),
            "reason": "the merged PR implemented it but its body carried no closing reference"}


def scan(repo: str, limit: int = 60) -> list[dict]:
    """Every finding across the recently merged PRs, newest first."""
    open_by_number = {i["number"]: i for i in open_issues(repo)}
    findings = []
    for pr in merged_prs(repo, limit):
        d = decide(pr, open_by_number)
        if d:
            d["mergedAt"] = pr.get("mergedAt")
            findings.append(d)
    findings.sort(key=lambda f: f.get("mergedAt") or "", reverse=True)
    return findings


def close_comment(f: dict) -> str:
    """The evidence comment posted before the issue is closed. Names the PR and what it left out."""
    return (
        f"Closed by the merged PR #{f['pr']} — the linkage its body missed.\n\n"
        f"#{f['pr']} implemented this issue ({f['evidence']}), but the body carried no `closes "
        f"#{f['issue']}`, so GitHub left it open. That is the case #325 exists to report: the in-repo "
        f"guard reads bodies and workflows, and cannot see what happened at PR time.\n\n"
        f"Any item the PR named under its own `Not covered` section stays tracked and open — those are "
        f"remainders, not missed closes.\n"
    )


def _claim(repo: str, issue: int) -> None:
    """Say we are starting, on the issue itself, before mutating it (issue #279)."""
    _gh(["issue", "comment", str(issue), "--repo", repo, "--body",
         bot_claims.claim_comment(CLEANER, "clean", datetime.now(timezone.utc),
                                  ttl=bot_claims.PR_CLAIM_TTL,
                                  run_id=None)])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--repo", required=True, help="owner/name")
    ap.add_argument("--limit", type=int, default=60, help="how many merged PRs to read")
    ap.add_argument("--dry", action="store_true", help="decide and print; close nothing")
    ap.add_argument("--json", action="store_true", help="emit the findings as JSON")
    a = ap.parse_args(argv)

    findings = scan(a.repo, a.limit)
    if a.json:
        print(json.dumps(findings, indent=2))
        return 0

    closes = [f for f in findings if f["action"] == "close"]
    remainders = [f for f in findings if f["action"] == "remainder"]
    for f in remainders:
        print(f"[cleaner] remainder #{f['issue']} ({f['title'][:60]}): {f['reason']}", flush=True)
    for f in closes:
        print(f"[cleaner] stale-open #{f['issue']} ({f['title'][:60]}): implemented by "
              f"#{f['pr']} per {f['evidence']}", flush=True)

    if not closes:
        print(f"[cleaner] nothing to close ({len(remainders)} tracked remainder(s))", flush=True)
        return 0
    if a.dry:
        print(f"[cleaner] --dry: {len(closes)} issue(s) would be closed; nothing mutated", flush=True)
        return 0

    for f in closes:
        _claim(a.repo, f["issue"])
        _gh(["issue", "comment", str(f["issue"]), "--repo", a.repo, "--body", close_comment(f)])
        _gh(["issue", "close", str(f["issue"]), "--repo", a.repo, "--reason", "completed"])
        print(f"[cleaner] closed #{f['issue']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
