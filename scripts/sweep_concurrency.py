#!/usr/bin/env python3
"""Report scheduled workflows that stack instead of superseding (issue #917).

A `schedule:` workflow fires again whether or not the previous run finished. With
`cancel-in-progress: false` the new run **waits** for the old one, so a slow sweep turns into a queue of
identical sweeps: measured on `auto-merge`, nine sweeps stacked between 22:36Z and 23:12Z and the bot became
12 of the 51 queued runs behind a 4h25m queue — the merger queued behind itself while green PRs sat armed and
BLOCKED.

Stacking is not always wrong: a sweep that mutates shared state (a registry sync, an engine build) may need
serialisation, and cancelling it mid-write is worse than waiting. That is a judgement per workflow, which is
why this is a REPORT and not a gate — but the judgement has to be **visible**, because the alternative is
what happened: nobody knew the merger was 12 runs deep until the queue was measured.

Usage:
    sweep_concurrency.py report [--root PATH]

Exit codes: 0 always — the report informs a decision, it does not take one.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def workflow_files(root: Path = REPO_ROOT) -> list[Path]:
    return sorted((root / ".github" / "workflows").glob("*.yml"))


def _block(text: str, key: str) -> str:
    """The indented body of a top-level `key:` mapping, as text — COMMENTS STRIPPED.

    The blocks in this tree carry their own explanation, and that prose quotes the very settings it argues
    about (`cancel-in-progress: false`, `head_branch`, …). A reader of the setting must not be satisfied or
    defeated by the words that explain it, so the decision is taken from the live lines only.
    """
    m = re.search(rf"^{key}:\s*\n((?:[ \t]+.*\n)+)", text, re.M)
    if not m:
        return ""
    return "\n".join(line for line in m.group(1).splitlines() if not line.lstrip().startswith("#"))


def classify(root: Path = REPO_ROOT) -> tuple[list[dict], list[dict]]:
    """`(stacking, superseding)`: scheduled workflows by whether a run can cancel the one before it."""
    stacking: list[dict] = []
    superseding: list[dict] = []
    for path in workflow_files(root):
        text = path.read_text()
        scheduled = bool(re.search(r"^  schedule:", text, re.M))
        if not scheduled:
            continue
        block = _block(text, "concurrency")
        group_match = re.search(r"group:\s*(.+)", block)
        cancel_match = re.search(r"cancel-in-progress:\s*(\w+)", block)
        entry = {"name": path.name,
                 "group": group_match.group(1).strip() if group_match else "",
                 "cancel": cancel_match.group(1) if cancel_match else None,
                 # A stacking workflow that SAYS why it serialises has been decided; one that is silent has
                 # not. The marker is greppable so the distinction survives a refactor, and the report can
                 # show progress instead of repeating the same fifteen names forever.
                 "decided": bool(re.search(r"#\s*concurrency:\s*stacking is intended", text))}
        cancels = "cancel-in-progress: true" in block
        if block and not cancels:
            stacking.append(entry)
        else:
            superseding.append(entry)
    return stacking, superseding


def report(root: Path = REPO_ROOT) -> str:
    stacking, superseding = classify(root)
    undecided = [e for e in stacking if not e["decided"]]
    decided = [e for e in stacking if e["decided"]]
    lines = [f"[sweep-concurrency] {len(undecided)} scheduled workflow(s) stack with no stated decision, "
             f"{len(decided)} stack on purpose, {len(superseding)} supersede"]
    for entry in undecided:
        lines.append(f"  UNDECIDED  {entry['name']}")
    for entry in decided:
        lines.append(f"  decided    {entry['name']}")
    if undecided:
        lines += [
            "",
            "why it costs: a scheduled sweep fires again on its slot whether or not the last one finished, so "
            "with no cancellation the new run WAITS for the old one instead of replacing it. Measured on "
            "auto-merge: nine sweeps stacked in 36 minutes and the bot became 12 of 51 queued runs behind a "
            "4h25m queue (issue #917).",
            "what to do: if the sweep only READS and then acts on fresh state, it is idempotent and "
            "`cancel-in-progress: true` is correct — the newer run subsumes the older. If it MUTATES shared "
            "state (a registry sync, an image build), serialising is right: keep `false` and say so in a "
            "comment beside the block, so the next reader knows it was decided rather than copied.",
        ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("report")
    p.add_argument("--root", default=str(REPO_ROOT))
    args = parser.parse_args(argv)

    print(report(Path(args.root)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
