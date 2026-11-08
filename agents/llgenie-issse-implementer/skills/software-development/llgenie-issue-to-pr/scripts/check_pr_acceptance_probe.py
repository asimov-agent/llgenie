#!/usr/bin/env python3
"""Print which linked-issue criteria `check-pr-acceptance` still flags.

Use it to prove a `## Not covered` exemption or a body edit LANDED before
spending a CI round-trip on guard+scope (which each invoke the same gate).

Usage (run from the repo root inside the pinned container, e.g.
`docker run --rm -u root -v "$PWD":/repo -w /repo llgenie/test:latest \
    python scripts/check_pr_acceptance_probe.py /tmp/issue.md /tmp/pr.md`):

    python3 scripts/check_pr_acceptance_probe.py <issue-body-file> <pr-body-file>

Fetch the live bodies first, e.g.:
    gh issue view <issue> --repo O/R --json body --jq .body > /tmp/issue.md
    gh pr view    <pr>    --repo O/R --json body --jq .body > /tmp/pr.md

Interpreting the output:
  - `violating_items` absent of a given index => that criterion is exempted
    (correct `## Not covered` bullet) or ticked. A paraphrase/one-line-broken
    bullet leaves the index in the set => the deflection is a no-op.
  - `keys=['acceptance-unchecked']` with the exempted index gone is the
    expected 'exemption landed' result; residual indexes are the reviewer-
    gated #1644/#1792 self-reds, not yours to tick.
"""
import os
import sys

# The script lives at <repo-root>/scripts/; put the repo root on sys.path so
# `from scripts import ...` resolves regardless of the caller's cwd.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts import check_pr_acceptance as g  # noqa: E402


def _items(verdict):
    items = []
    for v in verdict:
        ev = str(v.get("evidence", "")).split("(")[0]
        if "item " in ev:
            try:
                items.append(int(ev.split("item ")[1].split()[0]))
            except (IndexError, ValueError):
                pass
    return sorted(items)


def main(argv):
    if len(argv) != 3:
        print("usage: check_pr_acceptance_probe.py <issue-body-file> <pr-body-file>", file=sys.stderr)
        return 2
    with open(argv[1], encoding="utf-8") as fh:
        issue = fh.read()
    with open(argv[2], encoding="utf-8") as fh:
        pr = fh.read()
    verdict = g.acceptance_verdict(issue, pr) or []
    keys = sorted({v["key"] for v in verdict})
    print(f"keys={keys}")
    print(f"violating_items={_items(verdict)}")
    for v in verdict:
        print(f"  [{v['key']}] {v.get('evidence', '')}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
