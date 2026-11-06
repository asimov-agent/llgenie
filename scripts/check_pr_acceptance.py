#!/usr/bin/env python3
"""A merge must close an issue whose own acceptance criteria are checked — the issue-side gate (issue #1792).

`closes #N` proves the PR body NAMES the issue; it does not prove the issue's own "done" (issue #745:
a criterion a reviewer cannot tick is not one) was met. The only write-back — `acceptance_writeback.py`
(issue #1644) — is deliberately verdict-gated: an auto-merged PR with no reviewer verdict ticks
nothing (#1088-class), so an issue that merges 5/5 `- [ ]` stays honest and the merge verifies green.
This gate reads the LINKED ISSUE at merge time so that a close is not silently verified against nothing.

A tick is only as honest as the run behind it (issue #1858, audit #1857): a TICKED criterion must name
reproducible evidence — a named CI run (`run=<id>`), or a reproducible command + its exit code +
the measured tree sha (`proven: <command> rc=<n> <sha>`). A fold/sync tick that claims a hash/cmp or a
sync-check with no run id and no rc+sha is not re-verifiable from the issue thread alone, so the gate
reds it as `tick-unprovable` rather than trusting the text (#1784/#1819 class).

Commands:
    check_pr_acceptance.py check   exit non-zero when a PR's closed issue carries unticked
                                  `## Acceptance criteria`, when the PR body ticks a criterion the
                                  issue has unticked, or when a ticked criterion names no provable
                                  evidence (run id or reproducible command+rc+sha)
    check_pr_acceptance.py report  print the linked issues, their criterion counts and the verdict

Usage:
    python3 scripts/check_pr_acceptance.py check --body-file /tmp/pr-body.md --repo asimov-agent/llgenie
    python3 scripts/check_pr_acceptance.py check --body-file /tmp/pr-body.md --base origin/main --rev HEAD
    python3 scripts/check_pr_acceptance.py report --body-file /tmp/pr-body.md

The issue body is read LIVE (`gh api repos/<o>/<r>/issues/<n>`) at merge time — the issue-side
counterpart of the live PR-body reads `check-pr-closing`/`check-pr-agents-line` already do (issue
#1589). This is VERIFICATION, never write-back: the gate ticks nothing, it reports the discrepancy so
a lane/tool intended to prove the criteria can (that stays #1644's verdict-driven seam).

The linked-issue set is derived from the PR body AND, when `--base`/`--rev` are supplied, the joined
squash commit messages (issue #1815): GitHub's native close-on-merge reads the SQUASH TEXT, so a
`(closes #N)` that lives only in the commit messages is a real close that would auto-close a
multi-lane rollout umbrella with unticked criteria (measured 2026-11-05: #1813 `(closes #1812)`
auto-closed #1812 at 0/5, 1/3 lanes merged). The close parse is negation-aware — `does not close #N`
is NOT a close. When a close lives only in the squash text, the gate names it on-record
(`squash-only-close`) and still holds the umbrella via `acceptance_verdict`.
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
#: A close keyword that a preceding negation makes NON-closing (issue #1815): "does not close #N",
#: "won't close #N", "can't close #N", "without closing #N" are NOT closes. GitHub's native
#: close-on-merge is keyword-naive, so our parse must be negation-aware to tell a lane that is
#: deliberately NOT closing an umbrella from one that is — otherwise a "does not close #umbrella"
#: would be held to the umbrella's unticked criteria as if it had closed it.
NEGATED_CLOSE = re.compile(
    r"\b(?:does\s+not|do\s+not|don'?t|won'?t|will\s+not|shall\s+not|cannot|can'?t|never|"
    r"without|no\s+longer)\s+(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+#(\d+)",
    re.IGNORECASE,
)


def _closing_count(body: str) -> set[str]:
    """The issue ids a text closes, minus any a preceding negation renders NON-closing.

    This is the linked-issue set BOTH for the PR body and for the joined squash commit messages.
    `check_pr_closing.CLOSING` is GitHub's keyword-naive parse (a "closes #N" adjacency is what
    GitHub actually acts on); `NEGATED_CLOSE` subtracts the deliberate "does not close #N" a lane
    writes to avoid closing an umbrella when it only references it (issue #1815).
    """
    closed = set(cpc.closing_references(body or ""))
    negated = {m.group(1) for m in NEGATED_CLOSE.finditer(body or "")}
    return closed - negated


def linked_issue_numbers(body: str) -> list[int]:
    """Every issue a PR body actually closes (negation-aware, de-duplicated, sorted)."""
    return sorted({int(n) for n in _closing_count(body)})


def linked_squash_numbers(messages: list[str]) -> list[int]:
    """Every issue the joined squash commit messages close (negation-aware, sorted).

    The squash text is what GitHub's native close-on-merge actually reads (COMMIT_MESSAGES), so a
    `(closes #N)` that lives ONLY in the commit messages and NEVER in the PR body is a real close
    GitHub acts on — and before issue #1815 the acceptance gate never saw it.
    """
    return sorted({int(n) for n in _closing_count("\n\n".join(messages))})

#: The inline `(proven: …)` evidence a TICKED criterion carries (acceptance_writeback #1644).
PROVEN_MARKER = re.compile(r"\(proven:\s*(.*?)\)\s*$", re.S)
#: A named CI workflow run — `run=42191377162` — the strongest provable evidence (issue #1858).
RUN_ID = re.compile(r"\brun\s*=\s*\d+\b")
#: The reproducible fold/sync form: a command + its exit code + the measured tree sha, e.g.
#: `cmp live==tree <path> · agent_profile_sync --check PROFILE=x (rc 0, 4c3ac6f)`. A hash/compare
#: with no `rc=` (or no sha) is not re-measurable from the issue thread alone (#1784/#1819 class).
RC_SHA = re.compile(r"\brc(?:\s*=\s*|[\s(])\s*\S+\b")
GIT_SHA = re.compile(r"\b[0-9a-f]{7,40}\b")


def _is_provable_tick(text: str) -> bool:
    """True when a ticked criterion's `(proven: …)` names a CI run or a reproducible command+rc+sha."""
    m = PROVEN_MARKER.search(str(text or ""))
    if not m:
        return False  # a ticked box with no evidence is exactly the #745 self-tick class
    ref = m.group(1).strip()
    if RUN_ID.search(ref):
        return True  # a live named run is reproducible from the issue thread
    return bool(RC_SHA.search(ref) and GIT_SHA.search(ref))



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


def acceptance_verdict(issue_body_text: str, pr_body: str, issue: int) -> list[dict]:
    """The findings a merged PR closing `issue_body_text` carries.

    Two classes, exactly the dispatch's:
      * `claim-unchecked` — an acceptance criterion in the closed issue is still `- [ ]` and the PR
        body does not name it out of scope with a linked work item;
      * `claim-exceeds` — the PR body's own `- [x]` names a criterion the issue has UNTICKED.
    An issue with no `## Acceptance criteria` (or none tickable) returns no finding: nothing to prove.
    Every finding names the linked `#N` (`issue`) so a multi-issue PR's violations are distinguishable
    from a single CI log.
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
            "title": f"ci: a merged PR closes the issue #{issue} whose acceptance criterion is unchecked",
            "evidence": (
                f"acceptance item {pos} (\u201c{text[:80]}\u201d) is still `- [ ]` in the linked issue's "
                f"`## Acceptance criteria`, yet the PR body closes the issue. `closes #{issue}` proves the "
                f"PR names the issue, not that its own definition of done (issue #745) was met — the "
                f"only write-back is verdict-gated (#1644), so an un-reviewed merge stays honest. "
                f"Prove the criterion (tick it via `acceptance_writeback`) or name it out of scope "
                f"under `## Not covered` with a linked work item."
            ),
            "where": f"#{issue}",
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
            "title": f"ci: the PR body claims a ticked criterion the linked issue #{issue} still has unchecked",
            "evidence": (
                f"the PR body carries a `- [x]` for a criterion beginning \u201c{lead}\u201d that the "
                f"linked issue's `## Acceptance criteria` still has `- [ ]`. A merged PR must not "
                f"present as done what the issue it closes has not proven."
            ),
            "where": f"#{issue}",
        })

    # tick-unprovable: a TICKED criterion with no re-measurable evidence (issue #1858, #1784/#1819 class).
    for pos, _t, text in [it for it in items if it[1]]:
        m = PROVEN_MARKER.search(str(text or ""))
        ref = m.group(1).strip() if m else ""
        if _is_provable_tick(text):
            continue
        lack = (f"its `(proven: …)` names no CI run and no reproducible `command + rc=<n> + <sha>` "
                f"(measured text: \u201c{ref[:80]}\u201d)")
        out.append({
            "key": "tick-unprovable",
            "title": "ci: a ticked acceptance criterion names no replayable run id or reproducible command+rc+sha",
            "evidence": (
                f"acceptance item {pos} (\u201c{text[:80]}\u201d) is `- [x]` but {lack}. "
                f"A tick is only as honest as the run behind it (issue #745): it must name a CI run "
                f"(`run=<id>`) or a reproducible `proven: <command> rc=<n> <sha>` so a re-measurer "
                f"repeats one command, not a whole byte-compare. Fix the tick's evidence, or un-tick "
                f"it until a run/command actually proves it."
            ),
            "where": "issue-criteria-proof",
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
        c.add_argument("--base", default=None, help="git base of the squash range (PR_BASE; omit to skip the squash half)")
        c.add_argument("--rev", default="HEAD", help="git rev of the PR head (default HEAD)")
        c.add_argument("--cwd", default=None, help="repository the squash range is read from")
    args = p.parse_args(argv)
    body = args.body if args.body is not None else (
        Path(args.body_file).read_text() if args.body_file else "")
    closed = linked_issue_numbers(body)
    squash_notes: list[dict] = []
    squash_range_error: dict | None = None
    if args.base:
        cwd = Path(args.cwd) if args.cwd else REPO_ROOT
        try:
            messages = cpc.commit_messages(args.base, args.rev, cwd)
            squash_closed = linked_squash_numbers(messages)
            closed = sorted(set(closed) | set(squash_closed))
            # An umbrella whose close lives ONLY in the squash text (the text GitHub's native close
            # reads) is the exact premature-close hazard #1815 targets — name it. The HOLD that
            # blocks the merge is `acceptance_verdict` on the unticked umbrella (now included in
            # `closed`); this note is the on-record explanation, never an independent red.
            squash_only = sorted(set(squash_closed) - set(linked_issue_numbers(body)))
            for n in squash_only:
                squash_notes.append({
                    "key": "squash-only-close",
                    "title": "ci: a close keyword lives in the squash commit text but not the PR body",
                    "evidence": (
                        f"#{n} is adjacently closed by the joined squash commit messages but not by "
                        f"the PR body. GitHub's native close-on-merge reads the SQUASH TEXT, so this "
                        f"close WILL auto-close #{n} on merge even a multi-lane rollout umbrella whose "
                        f"criteria are still unticked (issue #1815, instance #1812). Keep the close on "
                        f"the FINAL lane only, when the umbrella's criteria are ticked."
                    ),
                    "where": "squash-commits",
                })
        except RuntimeError as exc:
            squash_range_error = {
                "key": "squash-range",
                "title": "ci: the squash range for the acceptance gate could not be read",
                "evidence": str(exc),
                "where": f"{args.base}..{args.rev}",
            }
    if args.cmd == "report":
        print(f"[check-pr-acceptance] linked issues: {', '.join(f'#{n}' for n in closed) or '(none)'}")
        for n in closed:
            try:
                items = _acceptance_items(_fetch_issue_body(args.gh, args.repo, n))
            except RuntimeError as exc:
                print(f"[check-pr-acceptance] #{n}: unreadable ({exc})")
                continue
            print(f"[check-pr-acceptance] #{n}: {len([i for i in items if i[1]])}/{len(items)} criteria ticked")
        if squash_range_error:
            print(f"[check-pr-acceptance] {squash_range_error['title']} — {squash_range_error['evidence']}")
        for f in squash_notes:
            print(f"[check-pr-acceptance] {f['title']} — {f['evidence']}")
        return 0
    items: list[dict] = []
    if squash_range_error:
        items.append(squash_range_error)
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
        items.extend(acceptance_verdict(issue, body, n))
    print(render(items))
    return 1 if items else 0


if __name__ == "__main__":
    raise SystemExit(main())
