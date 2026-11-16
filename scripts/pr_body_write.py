"""The guarded PR-body WRITE seam a bot leg routes every body replacement through (issue #2131).

`check-pr-acceptance` reads the LIVE PR body by design (issue #1589), so a lane's body is load-bearing
state: its `## Not covered` exemptions and its ticked `- [x]` items carrying `(proven: …)` are what the
gate reads and what a reviewer reads. Measured twice on PR #2113 (heads `ae4bb883`, `84b68fd7`): a
fix-bot repair push replaced the body with its own pre-fix copy, silently deleting the lane's `Not
covered` section and three proven ticks, and each deletion re-redded `ci-scope`
(`[check-pr-acceptance] 2 violation(s)`, runs `42448318954`, `42449007827`) on a head the lane had
already fixed — a rewrite invisible in the commit diff, and the red it created re-dispatched the bot.

This seam is the write-side guard. Before any body replacement it reads the live body through `gh` and
refuses the write when the proposed copy DROPS live content: a heading the proposal lacks, or a ticked
`- [x]` line carrying `(proven:` the proposal lacks. A refused write logs the skip, names every dropped
section on the PR as a comment, and exits 0 — the skip is the correct outcome, not a failure. An
identical proposal writes nothing (the #2050 re-stamp's `cmp` dance, made a property of the seam). Only
a proposal that preserves every such section reaches `gh pr edit`.

Shell producers reach it through `make bot-body-write PR=<n> [REPO=<o/r>] NEW=<body file>`; the stamp
authority (`bot_preflight.stamp_body`, #2050) stays where it is — this is the write guard around it,
not a second stamper.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import proc  # the ONE subprocess policy (issue #797): a failed gh is loud, never an empty string

#: A ticked acceptance line that carries its provenance — the state #2131 protects. The parser agrees
#: with `acceptance_writeback.PROVEN_SUFFIX`'s `(proven: ...)` shape, read from the LIVE body here.
PROVEN_TICK = r"^\s*-\s*\[[xX]\].*\(proven:"
#: Any markdown heading: a section the proposal would delete is exactly the #2131 deletion.
HEADING = r"^#{1,6}\s+\S"

_PROVEN_TICK = re.compile(PROVEN_TICK)
_HEADING = re.compile(HEADING)


def _live_items(text: str) -> list[str]:
    """The protected lines of a body, in order, deduped: headings and proven-ticked items."""
    seen: set[str] = set()
    out: list[str] = []
    for line in text.splitlines():
        if _HEADING.match(line) or _PROVEN_TICK.match(line):
            key = line.strip()
            if key not in seen:
                seen.add(key)
                out.append(key)
    return out


def body_preserve_findings(live: str, proposed: str) -> list[str]:
    """What the proposed body would DROP from the live body, as printable names (empty = safe write).

    Comparison is textual and cheap (the #2131 fix note's own metric): every heading line and every
    ticked `- [x] … (proven: …)` line the live body carries must appear, stripped, in the proposal.
    """
    kept = {line.strip() for line in proposed.splitlines()}
    return [item for item in _live_items(live) if item not in kept]


def skip_log(findings: list[str]) -> str:
    return (f"[pr-body-write] skip: the live body carries {len(findings)} item(s) the proposed body "
            f"drops — write refused (issue #2131): " + "; ".join(findings))


def skip_comment(findings: list[str]) -> str:
    lines = ["[pr-body-write] A bot leg offered a PR-body replacement that would DROP content the "
             "lane recorded here. The write was refused (issue #2131); the live body stands. Items "
             "the proposed copy lacked:", ""]
    lines += [f"- {item}" for item in findings]
    lines += ["", "_If the drop was intended, edit the body directly (a human body-edit is not a "
              "bot write) or restore the section before the next bot pass._"]
    return "\n".join(lines)


def _gh(repo: str, args: list[str]) -> str:
    return proc.run_text(["gh", *args, "--repo", repo])


def write_body(repo: str, pr_number: str, new_file: Path) -> int:
    """Guarded body-write for PR `pr_number`: refuse a dropping write, skip an equal one, else write."""
    proposed = Path(new_file).read_text()
    live = _gh(repo, ["pr", "view", str(pr_number), "--json", "body", "-q", ".body"])
    if proposed.rstrip() == live.rstrip():
        print("[pr-body-write] no write: the proposed body is identical to the live body.")
        return 0
    findings = body_preserve_findings(live, proposed)
    if findings:
        print(skip_log(findings))
        # The lane that owns the body must SEE the decision (issue #2131 AC3): the comment names each
        # dropped section. One argv string, no shell, no tempfile.
        _gh(repo, ["pr", "comment", str(pr_number), "--body", skip_comment(findings)])
        return 0
    _gh(repo, ["pr", "edit", str(pr_number), "--body-file", str(new_file)])
    print(f"[pr-body-write] wrote the body of PR #{pr_number}: every live section/proven tick is "
          "carried by the proposal.")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Guarded PR-body write seam (issue #2131)")
    ap.add_argument("--repo", required=True, help="owner/repo the PR lives in")
    ap.add_argument("--pr", required=True, help="the pull request number whose body is being written")
    ap.add_argument("--new", required=True, help="file holding the body proposed for the write")
    args = ap.parse_args(argv)
    if not Path(args.new).is_file():
        raise SystemExit(f"[pr-body-write] --new {args.new}: no such body file")
    return write_body(args.repo, args.pr, Path(args.new))


if __name__ == "__main__":
    sys.exit(main())
