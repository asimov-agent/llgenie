#!/usr/bin/env python3
"""A PR that implements an issue must close it — adjacent keyword in the body and in the squash text (issues #1329, #1417).

GitHub auto-closes an issue only when the pull request BODY carries `Fixes`/`Closes`/`Resolves`
adjacent to `#N`. This repository squash-merges with `squash_merge_commit_message=COMMIT_MESSAGES`,
so the commit that lands on main is the joined branch commit messages, not the pull request body.
Both texts have to carry the same adjacent close when the change claims an issue.

A claim is an `Issue: #N` line, or a commit subject or pull-request title that ends with `(#N)`.
Each claim must be an adjacent close in the joined messages. When the workflow supplies the body,
the body's adjacent-close set and the commit text's adjacent-close set are the same set. A change
that claims nothing and closes nothing passes. A `#N` that is only prose, including a remainder
under Not covered, is not a claim.

The older half still stands (issue #1329). An `agent/*` head whose body names an issue but holds
no adjacent closing keyword is red, and so is an `AGENTS.md` that lost the mandate. A markdown
wrapper (`closes **#N**`) is not a close: measured on #1328, which left #1327 open.

Commands:
    check_pr_closing.py check   exit non-zero when a claimed issue is not an adjacent close in the
                                squash text and the body, or when an agent/* body misses the keyword
    check_pr_closing.py report  print the body's closing references, the squash closes and the verdict

Usage:
    python3 scripts/check_pr_closing.py check --body-file /path/to/pr-body.md --base origin/main --rev HEAD
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.check_pr_authors import commits_in_range, _run  # noqa: E402

#: An `agent/*` head branch — the implementing-lane PR surface the body half guards.
AGENT_HEAD = re.compile(r"^agent/")
#: A closing reference as GitHub actually parses it: keyword + whitespace + `#<n>`, with NOTHING
#: between the keyword and the `#` but horizontal space. A `**` (markdown bold), a `:` or a comma is
#: not a separator GitHub recognises, so `closes **#1327**` and `closes:#1327` both MISS.
CLOSING = re.compile(
    r"\b(?:fix(?:e[sd])?|close[sd]?|resolve[sd]?)\s+#(\d+)(?![\w#])",
    re.IGNORECASE,
)
#: A bare reference `#N` anywhere — title, prose, a table cell.
ANY_REF = re.compile(r"#(\d+)")
#: `Issue: #N` at the start of a line. The same claim the issue cleaner reads off a merge commit.
ISSUE_LINE = re.compile(r"(?im)^\s*Issue:\s*#(\d+)\b")
#: A subject, or a pull-request title, that ends with `(#N)` and nothing after it but space.
SUBJECT_CLAIM = re.compile(r"\(#(\d+)\)\s*$")
#: The AGENTS.md section the rule must keep. Deleting it is a violation, not an edit.
AGENTS_MANDATE = "## A PR that implements an issue closes it — the keyword must be adjacent to #N in the body"


def closing_references(body: str) -> list[str]:
    """The issues a text actually closes: keyword ADJACENT to `#N`.

    A `**`, `:` or other separator between the keyword and `#N` is not returned. A bare `#N` is not
    a close.
    """
    return sorted({m.group(1) for m in CLOSING.finditer(body or "")}, key=int)


def referenced_issues(body: str) -> list[str]:
    """Every `#<n>` the text names, whatever the reason."""
    return [m.group(1) for m in ANY_REF.finditer(body or "")]


def issue_line_claims(text: str) -> set[str]:
    """Issue ids named by an `Issue: #N` line."""
    return {m.group(1) for m in ISSUE_LINE.finditer(text or "")}


def subject_claims(text: str) -> set[str]:
    """The issue id a subject or pull-request title claims by ending with `(#N)`."""
    subject = (text or "").split("\n", 1)[0].strip()
    match = SUBJECT_CLAIM.search(subject)
    return {match.group(1)} if match else set()


def claims_in(messages: list[str], body: str | None, title: str) -> set[str]:
    """Every claim the squash text, the optional body and the pull-request title make."""
    found: set[str] = set(subject_claims(title))
    for message in messages:
        found |= issue_line_claims(message)
        found |= subject_claims(message)
    if body is not None:
        found |= issue_line_claims(body)
    return found


def _fmt(nums: set[str]) -> str:
    if not nums:
        return "(none)"
    return ", ".join("#" + n for n in sorted(nums, key=int))


def check_squash(messages: list[str], body: str | None = None, title: str = "") -> list[dict]:
    """The joined commit messages are the squash body GitHub will write.

    `body is None` means the workflow did not supply a pull request body (a push to main, or a
    local run). The claim check still runs on the commit text. When `body` is a string, including
    an empty one, the two adjacent-close sets must match.
    """
    joined = "\n\n".join(messages)
    claimed = claims_in(messages, body, title)
    commit_closed = set(closing_references(joined))
    out: list[dict] = []
    missing_in_commits = sorted(claimed - commit_closed, key=int)
    if missing_in_commits:
        out.append({
            "key": "squash-commit",
            "title": "ci: the squash commit text does not adjacently close a claimed issue",
            "evidence": (
                f"The joined commit messages (the text GitHub writes as the squash body, "
                f"`COMMIT_MESSAGES`) claim {_fmt(set(missing_in_commits))} and do not carry an "
                f"adjacent `closes|fixes|resolves #N` for "
                f"{_fmt(set(missing_in_commits))}. A subject ending in `(#N)` or an `Issue: #N` "
                f"line is a claim. Add the adjacent close to the commit message."
            ),
            "where": "commits",
        })
    if body is None:
        return out
    body_closed = set(closing_references(body))
    missing_in_body = sorted(claimed - body_closed, key=int)
    if missing_in_body:
        out.append({
            "key": "squash-body",
            "title": "ci: the PR body does not adjacently close a claimed issue",
            "evidence": (
                f"The pull request body must adjacently close {_fmt(set(missing_in_body))}. "
                f"GitHub auto-close reads the body, and a claim (`Issue: #N` or a title ending "
                f"`(#N)`) is held to that keyword. `closes **#N**` does not close."
            ),
            "where": "pr-body",
        })
    if commit_closed != body_closed:
        out.append({
            "key": "squash-mismatch",
            "title": "ci: the squash commit text and the PR body close different issues",
            "evidence": (
                f"The joined commit messages close {_fmt(commit_closed)}. The pull request body "
                f"closes {_fmt(body_closed)}. Those sets have to be the same: the squash body is "
                f"what `git log` keeps, and the pull request body is what GitHub auto-closes from."
            ),
            "where": "commits+pr-body",
        })
    return out


def _merge_base(base: str, rev: str, cwd: Path) -> str:
    """The single merge-base of `base` and `rev`: the point the squash actually diverges from.

    `git merge-base <base> <rev>`'s first line is the common ancestor that bounds the commit set
    GitHub would squash. Using it instead of the literal range start keeps a PR whose head is a
    rebased/up-to-date branch from sweeping in main's own commits that a stale `base.sha` would
    include (issue #1527).
    """
    out = _run(["git", "merge-base", base, rev], cwd).strip()
    if not out:
        raise RuntimeError(f"git merge-base {base} {rev}: no common ancestor in {cwd}")
    return out.splitlines()[0]


def commit_messages(base: str, rev: str, cwd: Path = REPO_ROOT) -> list[str]:
    """Full messages of the non-merge commits the PR adds, the squash body stand-in.

    The range base is resolved to `git merge-base <base> <rev>` first, so the range is the commits
    the PR actually adds on top of the current base, NOT everything between an event-frozen
    `base.sha` and the head (issue #1527).
    """
    anchor = _merge_base(base, rev, cwd)
    return [row["message"] for row in commits_in_range(anchor, rev, cwd)]


def check_body(body_path: Path, head: str, root: Path = REPO_ROOT) -> list[dict]:
    """The body closes every issue it must, and only for an `agent/*` head surface.

    A non-`agent/*` head returns no finding from this half. An `agent/*` PR whose body names an
    issue but holds no ADJACENT closing keyword is a RED finding. The squash half is separate and
    applies to every head.
    """
    out: list[dict] = []
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
    if not head or not AGENT_HEAD.search(head):
        return out
    body = body_path.read_text() if body_path.exists() else ""
    closed = closing_references(body)
    if closed:
        return out
    named = referenced_issues(body)
    if named:
        out.append({
            "key": f"closing/{head}",
            "title": "ci: this agent PR names issue(s) but holds no adjacent closing keyword in its body",
            "evidence": (
                f"`{head}` names {', '.join('#' + n for n in named)} in its body but carries no "
                f"closing keyword adjacent to a reference. GitHub's auto-close requires the keyword in "
                f"the BODY directly before `#N` (e.g. `closes #1327`) — a bare `#` or `closes **#N**` "
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
                f"`{head}` implements no named issue (no '#' reference in its body) and closes none. "
                f"An `agent/*` PR is expected to name the issue it implements; if this is a pure chore, "
                f"open a tracking issue and close it from the body."
            ),
            "where": str(body_path),
        })
    return out


def render(items: list[dict]) -> str:
    if not items:
        return (
            "[check-pr-closing] OK — an agent PR body carries an adjacent closing keyword when that "
            "scope applies, and a claimed issue is closed in the squash text and the PR body"
        )
    lines = [f"[check-pr-closing] {len(items)} violation(s)"]
    for it in items:
        lines.append(f"  {it['title']}")
        lines.append(f"    {it['evidence']}")
    return "\n".join(lines)


def _resolved_title(arg: str | None) -> str:
    if arg is not None:
        return arg
    return os.environ.get("PR_TITLE", "")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="check_pr_closing", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("check", "report"):
        c = sub.add_parser(name)
        c.add_argument("--body-file", default=None, help="the file holding the PR body")
        c.add_argument("--head", default="", help="the PR head branch (agent/* is the body-half scope)")
        c.add_argument("--base", default=None, help="git base of the squash range (PR_BASE). Omit to skip the commit half")
        c.add_argument("--rev", default="HEAD", help="git rev of the PR head (default HEAD)")
        c.add_argument("--cwd", default=None, help="repository the range is read from")
        c.add_argument("--title", default=None, help="pull request title; defaults to the PR_TITLE environment variable")
    args = p.parse_args(argv)
    head = args.head or os.environ.get("PR_BRANCH", "")
    body = Path(args.body_file) if args.body_file else Path("/dev/null")
    cwd = Path(args.cwd) if args.cwd else REPO_ROOT
    title = _resolved_title(args.title)
    messages: list[str] = []
    range_error = ""
    if args.base:
        try:
            messages = commit_messages(args.base, args.rev, cwd)
        except RuntimeError as exc:
            range_error = str(exc)
    if args.cmd == "report":
        text = body.read_text() if body.exists() else ""
        named = referenced_issues(text)
        closed = closing_references(text)
        scope = "agent/*" if AGENT_HEAD.search(head) else "out of scope (not an agent/* head)"
        print(f"[check-pr-closing] head {head or '(none)'} primary check applies: {scope}")
        print(f"[check-pr-closing] closing references: {', '.join('#' + n for n in closed) or '(none)'}")
        print(f"[check-pr-closing] referenced issues:   {', '.join('#' + n for n in named) or '(none)'}")
        if args.base:
            if range_error:
                print(f"[check-pr-closing] commit range: {range_error}")
            else:
                joined = "\n\n".join(messages)
                supplied = text if args.body_file else None
                print(f"[check-pr-closing] squash closes: {_fmt(set(closing_references(joined)))}")
                print(f"[check-pr-closing] claims: {_fmt(claims_in(messages, supplied, title))}")
        return 0
    items = check_body(body, head)
    if range_error:
        items.append({
            "key": "commit-range",
            "title": "ci: the commit range for the squash text could not be read",
            "evidence": range_error,
            "where": f"{args.base}..{args.rev}",
        })
    elif args.base:
        supplied = body.read_text() if args.body_file and body.exists() else ("" if args.body_file else None)
        items.extend(check_squash(messages, supplied, title))
    print(render(items))
    return 1 if items else 0


if __name__ == "__main__":
    raise SystemExit(main())
