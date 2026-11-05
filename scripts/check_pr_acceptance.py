#!/usr/bin/env python3
"""A merge must close an issue whose own acceptance criteria are checked — the issue-side gate (issue #1792).

`closes #N` proves the PR body NAMES the issue; it does not prove the issue's own "done" (issue #745:
a criterion a reviewer cannot tick is not one) was met. The only write-back — `acceptance_writeback.py`
(issue #1644) — is deliberately verdict-gated: an auto-merged PR with no reviewer verdict ticks
nothing (#1088-class), so an issue that merges 5/5 `- [ ]` stays honest and the merge verifies green.
This gate reads the LINKED ISSUE at merge time so that a close is not silently verified against nothing.

Commands:
    check_pr_acceptance.py check   exit non-zero when a PR's closed issue carries unticked
                                  `## Acceptance criteria`, or when the PR body ticks a criterion the
                                  issue has unticked
    check_pr_acceptance.py report  print the linked issues, their criterion counts and the verdict

Usage:
    python3 scripts/check_pr_acceptance.py check --body-file /tmp/pr-body.md --repo asimov-agent/llgenie
    python3 scripts/check_pr_acceptance.py report --body-file /tmp/pr-body.md

The issue body is read LIVE (`gh api repos/<o>/<r>/issues/<n>`) at merge time — the issue-side
counterpart of the live PR-body reads `check-pr-closing`/`check-pr-agents-line` already do (issue
#1589). This is VERIFICATION, never write-back: the gate ticks nothing, it reports the discrepancy so
a lane/tool intended to prove the criteria can (that stays #1644's verdict-driven seam).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from scripts import check_pr_closing as cpc  # noqa: E402  the linked-issue set (closing_references)
from scripts.acceptance_writeback import CHECKBOX_RE  # noqa: E402  the issue checkbox parse, reused
from scripts import issue_body  # noqa: E402  the ## Acceptance criteria section scope
from scripts import proc  # noqa: E402  the ONE subprocess seam (issue #797)

BASE_REPO = "asimov-agent/llgenie"
#: A PR body marking a criterion out of scope with its own linked work item (issue #1792): a
#: `## Not covered` bullet that names a `#<n>` reference. The repo issue shape already reserves that
#: section for exactly this ("out-of-scope work is its own linked issue", issue_body.OPTIONAL_SECTION).
OUT_OF_SCOPE = re.compile(r"(?im)^-.*\s*#\d+\s*$")


def _acceptance_items(body: str) -> list[tuple[int, bool, str]]:
    """Every acceptance item (1-based position, ticked?, text) inside `## Acceptance criteria`.

    Only items in that section count — a checkbox in a Technical block or a PR-body Verify list is not
    an issue criterion (issue #745). Reuses `acceptance_writeback.CHECKBOX_RE` + `issue_body.section_body`,
    the two sources the write-back seam and the issue renderer already mount.
    """
    section = issue_body.section_body(str(body or ""), "Acceptance criteria")
    if not section:
        return []
    items: list[tuple[int, bool, str]] = []
    for line in section.splitlines():
        m = CHECKBOX_RE.match(line)
        if not m:
            continue
        ticked = m.group("state").strip().lower() == "x"
        items.append((len(items) + 1, ticked, m.group("rest").strip()))
    return items


def _declared_out_of_scope(pr_body: str, criterion: str) -> bool:
    """True when the PR body marks `criterion` out of scope by naming a linked `#<n>` under `## Not covered`.

    The exemption the dispatch allows: a criterion the PR claims is unchecked is held UNLESS the PR
    body explicitly names it as out of scope with a linked work item. We match the criterion's leading
    words (normalised) beside a `#<n>` in the `## Not covered` section — a bare claim with no linked
    work item does not count, because an empty exemption is an empty gate.
    """
    covered = issue_body.section_body(str(pr_body or ""), "Not covered")
    if not covered:
        return False
    if not OUT_OF_SCOPE.search(covered):
        return False
    words = re.split(r"\s+", re.sub(r"[^A-Za-z0-9 ]", " ", criterion).strip().lower())
    lead = " ".join(words[:3]).strip()
    nc = re.sub(r"[^A-Za-z0-9 ]", " ", covered).lower()
    return bool(lead and lead in nc)


def acceptance_verdict(issue_body_text: str, pr_body: str) -> list[dict]:
    """The findings a merged PR closing `issue_body_text` carries.

    Two classes, exactly the dispatch's:
      * `claim-unchecked` — an acceptance criterion in the closed issue is still `- [ ]` and the PR
        body does not name it out of scope with a linked work item;
      * `claim-exceeds` — the PR body's own `- [x]` names a criterion the issue has UNTICKED.
    An issue with no `## Acceptance criteria` (or none tickable) returns no finding: nothing to prove.
    """
    items = _acceptance_items(issue_body_text)
    if not items:
        return []
    out: list[dict] = []
    unticked = [it for it in items if not it[1]]

    # claim-unchecked: the close is held while unproven criteria stay unticked, unless out-of-scope.
    for pos, _t, text in unticked:
        if _declared_out_of_scope(pr_body, text):
            continue
        out.append({
            "key": "acceptance-unchecked",
            "title": "ci: a merged PR closes an issue whose acceptance criterion is unchecked",
            "evidence": (
                f"acceptance item {pos} (\u201c{text[:80]}\u201d) is still `- [ ]` in the linked issue's "
                f"`## Acceptance criteria`, yet the PR body closes the issue. `closes #<n>` proves the "
                f"PR names the issue, not that its own definition of done (issue #745) was met — the "
                f"only write-back is verdict-gated (#1644), so an un-reviewed merge stays honest. "
                f"Prove the criterion (tick it via `acceptance_writeback`) or name it out of scope "
                f"under `## Not covered` with a linked work item."
            ),
            "where": "issue-criteria",
        })

    # claim-exceeds: the PR body ticks a box the issue still has open.
    pr_checked_lead = {
        re.split(r"\s+", it[2].lower())[0] for it in _pr_checkboxes(pr_body) if it[1]
    }
    issue_unticked_lead = {text.split()[0].strip("`*_-. ") for pos, _t, text in unticked}
    overlap = pr_checked_lead & issue_unticked_lead
    for lead in sorted(overlap):
        out.append({
            "key": "acceptance-exceeds",
            "title": "ci: the PR body claims a ticked criterion the linked issue still has unchecked",
            "evidence": (
                f"the PR body carries a `- [x]` for a criterion beginning \u201c{lead}\u201d that the "
                f"linked issue's `## Acceptance criteria` still has `- [ ]`. A merged PR must not "
                f"present as done what the issue it closes has not proven."
            ),
            "where": "pr-body-vs-issue",
        })
    return out


def _pr_checkboxes(body: str) -> list[tuple[int, bool, str]]:
    """The PR body's OWN `- [x]`/`- [ ]` list: the body-side claim of what is done (issue #1792)."""
    items: list[tuple[int, bool, str]] = []
    for line in str(body or "").splitlines():
        m = CHECKBOX_RE.match(line)
        if not m:
            continue
        ticked = m.group("state").strip().lower() == "x"
        items.append((len(items) + 1, ticked, m.group("rest").strip()))
    return items


def _fetch_issue_body(gh: str, repo: str, issue: int) -> str:
    """The live issue body — the merge-tip measure, never a cached copy."""
    try:
        stdout = proc.run_checked([gh, "issue", "view", str(issue), "--repo", repo, "--json", "body"])
    except proc.ProcError as exc:
        raise RuntimeError(
            f"gh issue view {issue} failed ({exc.returncode}): {(exc.stderr or exc.stdout).strip()}"
        ) from exc
    return json.loads(stdout)["body"]


def render(items: list[dict]) -> str:
    if not items:
        return "[check-pr-acceptance] OK — every closed issue's `## Acceptance criteria` is checked or named out of scope"
    lines = [f"[check-pr-acceptance] {len(items)} violation(s)"]
    for it in items:
        lines.append(f"  {it['title']}")
        lines.append(f"    {it['evidence']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="check_pr_acceptance", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("check", "report"):
        c = sub.add_parser(name)
        c.add_argument("--body-file", default=None, help="the file holding the PR body (LIVE, issue #1589)")
        c.add_argument("--body", default=None, help="the PR body as a literal string (tests)")
        c.add_argument("--repo", default=BASE_REPO, help="the repo the issues live in (default %(default)s)")
        c.add_argument("--gh", default="gh")
    args = p.parse_args(argv)
    body = args.body if args.body is not None else (
        Path(args.body_file).read_text() if args.body_file else "")
    closed = [int(n) for n in cpc.closing_references(body)]
    if args.cmd == "report":
        print(f"[check-pr-acceptance] linked issues: {', '.join(f'#{n}' for n in closed) or '(none)'}")
        for n in closed:
            try:
                items = _acceptance_items(_fetch_issue_body(args.gh, args.repo, n))
            except RuntimeError as exc:
                print(f"[check-pr-acceptance] #{n}: unreadable ({exc})")
                continue
            print(f"[check-pr-acceptance] #{n}: {len([i for i in items if i[1]])}/{len(items)} criteria ticked")
        return 0
    items: list[dict] = []
    for n in closed:
        try:
            issue = _fetch_issue_body(args.gh, args.repo, n)
        except RuntimeError as exc:
            items.append({
                "key": "issue-unreadable",
                "title": f"ci: the linked issue #{n} could not be read at merge time",
                "evidence": str(exc),
                "where": f"#{n}",
            })
            continue
        items.extend(acceptance_verdict(issue, body))
    print(render(items))
    return 1 if items else 0


if __name__ == "__main__":
    raise SystemExit(main())
