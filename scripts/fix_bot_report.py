"""Print a short, PR-commentable summary of a fix-bot round (issue #222).

The workflow comments this on the PR when the loop gives up, so the failing lines are in
front of a human without anyone opening the job log. Reads the loop's report file and
prints the last `--lines` lines, fenced, with the command that produced them.
"""
from __future__ import annotations

import argparse
import pathlib


def summarize(report: pathlib.Path, command: str, lines: int = 30) -> str:
    """Markdown for a PR comment: the command, its tail, and what to do next."""
    tail = report.read_text(errors="replace").splitlines()[-lines:] if report.exists() else []
    body = "\n".join(tail) or "(the report file was empty)"
    return (
        f"The fix-bot ran `{command}` and it is still failing after its repair attempts.\n\n"
        f"```\n{body}\n```\n\n"
        "Leaving this PR for a human: the loop never weakens, skips or deletes a check, and it "
        "does not merge. [issue #222]"
    )


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("report", type=pathlib.Path, help="the loop's report file")
    ap.add_argument("--command", default="make ci-unit", help="the check command that failed")
    ap.add_argument("--lines", type=int, default=30, help="how many trailing lines to include")
    a = ap.parse_args(argv)
    print(summarize(a.report, a.command, a.lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
