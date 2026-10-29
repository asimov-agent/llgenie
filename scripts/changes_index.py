#!/usr/bin/env python3
"""The change index is a DIRECTORY of one-row files, not a shared table (issue #934)

A change used to add its row to the top of `CHANGES.md`. That is a single append point: every
open PR edits the same file at the same line, so every merge re-dirties every other PR (measured
2026-10-29 at `main@97a24063`: 20 of 31 open PRs read `DIRTY`, 16 of them in `CHANGES.md` alone),
and a DIRTY PR gets no CI run at all — verified work could not receive a verdict.

So the index is now **one file per change**: `docs/changes.d/<note-stem>.md`, holding exactly one
row. Two changes add two different files, so git has nothing to conflict on. `CHANGES.md` is
**rendered** from those fragments by `make changes-index`; no change PR writes it.

  changes_index.py check    exit 1 on a note with no fragment, a fragment whose note is gone, or a
                            malformed row (the row must carry a date, a summary, the note link and
                            an issue/PR reference)
  changes_index.py render   print the rendered `CHANGES.md`
  changes_index.py write    write `CHANGES.md` from the fragments (what `make changes-index` runs)
  changes_index.py report   print the fragment census and how far `CHANGES.md` is behind them

`CHANGES.md` stays a committed file a reader can open on GitHub. It is not a merge surface: the
gate never requires it to be current, so a change PR never has to touch it. The documentation lane
refreshes it (`make changes-index`); `report` names the gap meanwhile.

Stdlib only.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FRAGMENTS = "docs/changes.d"
CHANGES = "CHANGES.md"
WIKI_DIR = "agent-wiki"

#: One row: `| date | summary | [note](agent-wiki/<stem>.md) | #issue |`.
ROW_RE = re.compile(
    r"^\|\s*(?P<date>[^|]*?)\s*\|(?P<summary>.+?)\|"
    r"\s*\[[^\]]*\]\(\.?/?agent-wiki/(?P<note>[^)\s]+\.md)\)\s*\|"
    r"(?P<refs>[^|]+?)\s*\|\s*$"
)
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
REF_RE = re.compile(r"#\d+|\b(?:issue|issues|pr|PRs?)\s+#?\d+", re.I)
TABLE_HEAD = "| Date | Change | Record | Issue / PR |\n|---|---|---|---|\n"

HEADER = (
    "# Changes — the index of change records\n"
    "\n"
    "Every change in this repository has ONE dated note of its own in `agent-wiki/` — a Zettelkasten\n"
    "entry that states what was verified against the spec, the decisions taken, and the issue and PR\n"
    "it implements. This file is the index of those notes, newest first, and it is the file\n"
    "`README.md` points at instead of carrying change history itself.\n"
    "\n"
    "The index rows do not live here: each one is its own file, `docs/changes.d/<note-stem>.md`,\n"
    "holding a single row (issue #934). A change adds its note and its fragment, and nothing else.\n"
    "One row per file means two changes can never edit the same line, so no merge can re-dirty an\n"
    "open PR. This page is rendered from those fragments by `make changes-index`; do not edit it by\n"
    "hand.\n"
    "\n"
    "`make check-docs` fails when a note under `agent-wiki/` has no fragment, when a fragment names\n"
    "a note that does not exist, or when a row is malformed.\n"
    "\n"
)


def _stems(root: Path) -> dict[str, str]:
    """`{note stem: fragment text}` for every `docs/changes.d/*.md` file."""
    d = root / FRAGMENTS
    if not d.is_dir():
        return {}
    return {p.stem: p.read_text() for p in sorted(d.glob("*.md"))}


def _notes(root: Path) -> dict[str, str]:
    """`{note stem: note text}` for every `agent-wiki/*.md` work record."""
    d = root / WIKI_DIR
    if not d.is_dir():
        return {}
    return {p.stem: p.read_text() for p in sorted(d.glob("*.md"))}


def parse_row(text: str, stem: str) -> tuple[dict | None, list[str]]:
    """One fragment's single row, or the reasons it is not one."""
    body = [line for line in text.splitlines() if line.strip()]
    if len(body) != 1:
        return None, [f"{FRAGMENTS}/{stem}.md: holds {len(body)} line(s); a fragment is exactly one row"]
    m = ROW_RE.match(body[0])
    if not m:
        return None, [
            f"{FRAGMENTS}/{stem}.md: is not a row "
            "(shape: `| date | summary | [note](agent-wiki/<stem>.md) | #issue |`)"
        ]
    errors: list[str] = []
    if not DATE_RE.match(m.group("date")):
        errors.append(f"{FRAGMENTS}/{stem}.md: date {m.group('date')!r} is not YYYY-MM-DD")
    if m.group("note") != f"{stem}.md":
        errors.append(
            f"{FRAGMENTS}/{stem}.md: links agent-wiki/{m.group('note')}, and a fragment must index "
            f"the note of its own name (agent-wiki/{stem}.md)"
        )
    if not REF_RE.search(m.group("refs")):
        errors.append(f"{FRAGMENTS}/{stem}.md: names no issue or PR in its `Issue / PR` cell")
    if errors:
        return None, errors
    return {
        "date": m.group("date"),
        "summary": m.group("summary").strip(),
        "note": m.group("note"),
        "refs": m.group("refs").strip(),
    }, []


def rows(root: Path = REPO) -> tuple[list[dict], list[str]]:
    """Every parsed row (newest first) and every fragment defect."""
    parsed: list[dict] = []
    errors: list[str] = []
    for stem, text in _stems(root).items():
        row, errs = parse_row(text, stem)
        errors.extend(errs)
        if row:
            parsed.append(row | {"stem": stem})
    parsed.sort(key=lambda r: (r["date"], r["stem"]), reverse=True)
    return parsed, errors


def check(root: Path = REPO) -> list[str]:
    """Every index defect: an unindexed note, a fragment with no note, a malformed row."""
    parsed, errors = rows(root)
    notes = _notes(root)
    indexed = {r["stem"] for r in parsed}
    for stem in notes:
        if stem not in indexed:
            errors.append(
                f"{WIKI_DIR}/{stem}.md: is not indexed — add {FRAGMENTS}/{stem}.md with its row"
            )
    for stem in _stems(root):
        if stem not in notes:
            errors.append(f"{FRAGMENTS}/{stem}.md: links {WIKI_DIR}/{stem}.md, which does not exist")
    return errors


def render(root: Path = REPO) -> str:
    """The rendered `CHANGES.md`: the header plus every fragment's row, newest first."""
    parsed, _ = rows(root)
    body = "".join(
        f"| {r['date']} | {r['summary']} | [{r['note']}]({WIKI_DIR}/{r['note']}) | {r['refs']} |\n"
        for r in parsed
    )
    return HEADER + TABLE_HEAD + body


def write(root: Path = REPO) -> int:
    """Render `CHANGES.md` from the fragments. What `make changes-index` runs."""
    errors = check(root)
    if errors:
        for err in errors:
            print(f"[changes-index] ERROR: {err}", file=sys.stderr)
        print(f"[changes-index] {len(errors)} problem(s); CHANGES.md not written", file=sys.stderr)
        return 1
    path = root / CHANGES
    text = render(root)
    path.write_text(text)
    print(f"[changes-index] wrote {path} from {len(_stems(root))} fragment(s)")
    return 0


def report(root: Path = REPO) -> str:
    """The fragment census, plus how many rows `CHANGES.md` is behind."""
    parsed, errors = rows(root)
    notes = _notes(root)
    on_disk = _stems(root)
    rendered = render(root)
    committed = (root / CHANGES).read_text() if (root / CHANGES).exists() else ""
    committed_rows = [l for l in committed.splitlines() if l.startswith("|") and not l.startswith("|---")
                      and not l.startswith("| Date")]
    lines = [
        f"[changes-index] {root}",
        f"[changes-index] {len(on_disk)} fragment(s) in {FRAGMENTS}/, {len(notes)} note(s) in "
        f"{WIKI_DIR}/, {len(parsed)} row(s) parsed, {len(errors)} defect(s)",
        f"[changes-index] {CHANGES}: {len(committed_rows)} row(s) committed, "
        f"{len(parsed)} rendered — "
        + ("current" if committed == rendered else f"{abs(len(parsed) - len(committed_rows))} row(s) behind"),
    ]
    lines.extend(f"[changes-index]   {err}" for err in errors)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="changes_index.py", description=__doc__)
    parser.add_argument("mode", choices=("check", "render", "write", "report"))
    parser.add_argument("--root", default=str(REPO), help="checkout to read (default: this repo)")
    args = parser.parse_args(argv)
    root = Path(args.root)
    if args.mode == "render":
        print(render(root), end="")
        return 0
    if args.mode == "write":
        return write(root)
    if args.mode == "report":
        print(report(root))
        return 0
    errors = check(root)
    for err in errors:
        print(f"[changes-index] ERROR: {err}", file=sys.stderr)
    if errors:
        print(f"[changes-index] {len(errors)} problem(s); see `make changes-index-report`", file=sys.stderr)
        return 1
    print(f"[changes-index] ok: {len(_stems(root))} fragment(s) index every {WIKI_DIR}/ note, "
          "and every fragment indexes a note that exists")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
