#!/usr/bin/env python3
"""A PR that implements an issue must close it in its body — the closing keyword is the contract (issue #1329).

A merged PR that does not carry a GitHub closing keyword in its BODY leaves the issue OPEN forever:
GitHub's auto-close fires only on a keyword (`Fixes`/`Closes`/`Resolves` / `fixes`/`closes`/`resolves`
…) **adjacent** to an issue reference `#N` in the body. A bare `#N` in the title, or the number only in
the first-line prose, does NOT trigger it — and the keyword must be DIRECTLY followed by the reference.

Measured on main `010ea8d9`:

* **#1328** (round-10 fold, MERGED -> `010ea8d9`) left **#1327 OPEN** although its body ends with the
  words `Addresses and closes **#1327**`. The `**` between `closes` and `#1327` is markdown, not a
  separating space, so GitHub's reference parser does not see `closes #1327`: the reference is never
  linked, and the issue is never auto-closed (`stateReason:""`, `closedAt:null`).
* **#1326** closed **#1322** correctly because its body's first line is `Fixes #1322` — keyword
  directly followed by the reference, nothing between them.

The gate mirrors that parser. It reads a PR's body and asserts that, for a PR on an `agent/*` head
branch (the implementing-lane surface), the body carries at least one closing keyword adjacent to an
issue reference. A branch that is not `agent/*` is out of scope (the owner's direct pushes, charts,
renovate bumps) — the check is a subset test, never a roster of issues.

GitHub's parser allows optional lowercase/uppercase and the `&` form; the rule enforced here is the
plain adjacency: keyword `\\s+` `#<digits>`, nothing else between them. A markdown wrapper (`**#N**`),
a colon (`closes: #N` — GitHub accepts the bare keyword but not every separator), or a comma is not a
closing reference and is reported as a miss, because it is a miss on GitHub.

Commands:
    check_pr_closing.py check   exit non-zero and list the body, branch and defect when an `agent/*`
                                PR carries no adjacent closing keyword (or AGENTS.md lost the mandate)
    check_pr_closing.py report  print the body's closing references and the verdict

Usage:
    python3 scripts/check_pr_closing.py check --body-file /path/to/pr-body.md --head agent/issue-123
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
#: An `agent/*` head branch — the implementing-lane PR surface this gate guards.
AGENT_HEAD = re.compile(r"^agent/")
#: A closing reference as GitHub actually parses it: keyword + whitespace + `#<n>`, with NOTHING
#: between the keyword and the `#` but horizontal space. A `**` (markdown bold), a `:` or a comma is
#: not a separator GitHub recognises, so `closes **#1327**` and `closes:#1327` both MISS. The keywords
#: cover each verb's active forms: fix/fixes/fixed, close/closes/closed, resolve/resolves/resolved.
CLOSING = re.compile(
    r"\b(?:fix(?:e[sd])?|close[sd]?|resolve[sd]?)\s+#(\d+)(?![\w#])",
    re.IGNORECASE,
)
#: A bare reference `#N` anywhere — title, prose, a table cell. It proves the PR *names* an issue
#: even when no closing keyword links it, which is what the miss report must name.
ANY_REF = re.compile(r"#(\d+)")
#: The AGENTS.md section the rule must keep. Deleting it is a violation, not an edit (the same
#: mandate-half shape as `check_pr_authors`).
AGENTS_MANDATE = "## A PR that implements an issue closes it — the keyword must be adjacent to #N in the body"


def closing_references(body: str) -> list[str]:
    """The issues a body actually closes: `fixes|closes|resolves #N`, keyword ADJACENT to the ref.

    Adjacency is the whole rule: a `**` (markdown), `:` or trailing separator between the keyword and
    `#N` is a reference GitHub does not close (the measured #1328 / #1327 failure), so it is NOT
    returned here. A leading `#` with no keyword, or the number only in a title/table, is likewise not
    a close.
    """
    return sorted({m.group(1) for m in CLOSING.finditer(body)})


def referenced_issues(body: str) -> list[str]:
    """Every `#<n>` the body names, whatever the reason — what the miss report attributes the open to."""
    return [m.group(1) for m in ANY_REF.finditer(body)]


def check_body(body_path: Path, head: str, root: Path = REPO_ROOT) -> list[dict]:
    """The body closes every issue it must, and only for an `agent/*` head surface.

    A non-`agent/*` head is out of scope and returns no finding — this gate guards the implementing
    lane, never the owner's direct pushes, charts or renovate bumps. An `agent/*` PR whose body names
    an issue but holds no ADJACENT closing keyword is a RED finding; the report names the issues the
    body references so a lane sees precisely what GitHub will leave open.
    """
    out: list[dict] = []
    # The AGENTS.md mandate must stand in every mode, PR-scope or not (the same shape as the
    # `check_pr_authors` static half): deleting the rule is a violation, not an edit.
    agents = root / "AGENTS.md"
    if agents.exists() and AGENTS_MANDATE not in agents.read_text():
        out.append({
            "key": "agents-mandate",
            "title": "ci: AGENTS.md lost the adjacent-closing-keyword mandate",
            "evidence": (
                f"`{AGENTS_MANDATE}` is gone from `AGENTS.md`. Deleting the rule is a violation, not "
                f"an edit — a merged PR without an adjacent closing keyword leaves its issue OPEN."
            ),
            "where": "AGENTS.md",
        })
    # The body half applies ONLY to an `agent/*` head — the implementing-lane surface this gate
    # guards. The owner's own branches (charts, renovate bumps, direct pushes) are out of scope.
    if not head or not AGENT_HEAD.search(head):
        return out
    body = body_path.read_text() if body_path.exists() else ""
    closed = closing_references(body)
    if closed:
        return out
    named = referenced_issues(body)
    # The named-issues list is the miss the gate is here to catch.
    if named:
        out.append({
            "key": f"closing/{head}",
            "title": "ci: this agent PR names issue(s) but holds no adjacent closing keyword in its body",
            "evidence": (
                f"`{head}` names {', '.join('#' + n for n in named)} in its body but carries no "
                f"closing keyword adjacent to a reference. GitHub's auto-close requires the keyword in "
                f"the BODY directly before `#N` (e.g. `closes #1327`) — a bare `#'s` or `closes **#N**` "
                f"(markdown between the keyword and the ref) does NOT close (measured: #1328 left #1327 "
                f"open). Add `closes #<n>` to the body and push."
            ),
            "where": str(body_path),
        })
    elif not body.strip():
        out.append({
            "key": f"empty-body/{head}",
            "title": "ci: this agent PR has no body to name or close its issue",
            "evidence": (
                f"`{head}` has an empty body. An `agent/*` PR implements an issue; its body must carry "
                f"`closes #<n>`. GitHub will not auto-close the issue from a title or an empty body."
            ),
            "where": str(body_path),
        })
    else:
        out.append({
            "key": f"no-ref/{head}",
            "title": "ci: this agent PR names no issue and closes none",
            "evidence": (
                f"`{head}` implements no named issue (`no '#' reference in its body`) and closes none. "
                f"An `agent/*` PR is expected to name the issue it implements; if this is a pure chore, "
                f"open a tracking issue and close it from the body."
            ),
            "where": str(body_path),
        })
    return out


def render(items: list[dict]) -> str:
    if not items:
        return "[check-pr-closing] OK — every agent PR body carries an adjacent closing keyword (or is not an agent PR)"
    lines = [f"[check-pr-closing] {len(items)} violation(s)"]
    for it in items:
        lines.append(f"  {it['title']}")
        lines.append(f"    {it['evidence']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="check_pr_closing", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("check", "report"):
        c = sub.add_parser(name)
        c.add_argument("--body-file", default=None, help="the file holding the PR body")
        c.add_argument("--head", default="", help="the PR head branch (default: '' — out of scope)")
    args = p.parse_args(argv)
    body = Path(args.body_file) if args.body_file else Path("/dev/null")
    if args.cmd == "report":
        named = referenced_issues(body.read_text() if body.exists() else "")
        closed = closing_references(body.read_text() if body.exists() else "")
        scope = "agent/*" if AGENT_HEAD.search(args.head) else "out of scope (not an agent/* head)"
        print(f"[check-pr-closing] head {args.head or '(none)'} primary check applies: {scope}")
        print(f"[check-pr-closing] closing references: {', '.join('#' + n for n in closed) or '(none)'}")
        print(f"[check-pr-closing] referenced issues:   {', '.join('#' + n for n in named) or '(none)'}")
        return 0
    items = check_body(body, args.head)
    print(render(items))
    return 1 if items else 0


if __name__ == "__main__":
    raise SystemExit(main())
