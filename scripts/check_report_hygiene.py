#!/usr/bin/env python3
"""A reporting leg names the evidence (a sha) or stays silent about ownership (issue #1292).

A finding in this fleet is measured at a sha and names its evidence. Ownership-blame is the one
measurement a harness cannot make from a diff — a changed file has no author-of-record in the commit
graph — so "another lane advanced it", "someone else moved the head" or any blame sentence that says
*whose* work did an adverse thing is always a guess unless a specific sha is named. `agent_profile_sync.py`
already states the corrected principle in prose ("the tree has no ownership information, so never say whose
work it is"), and `orchestrator_tick.py` frames the same failure as an order-of-operations — but neither is
a tree-enforced guard. This check makes evidence-or-silence structural:

- it scans the tree's **reporting legs** — the strings a `scripts/*.py` actually *emits* (string constants
  and f-string literal fragments, excluding docstrings), plus workflow step `name:`/`run:` lines in
  `.github/workflows/*.yml`;
- a reporting string that pairs an **ownership pronoun** (another lane, the other lane, a sibling lane,
  someone else, this lane, ...) with an **adverse shared-state change verb** (advanced, rewrote, moved,
  overwrote, pushed, edited, challenged, deleted, ...) is a blame sentence;
- the sentence is a **violation** unless a `@<sha>`, `$<sha>` or bare sha evidence anchor sits on the same
  line. A sha-tagged sentence passes; prose with no blame (a comment, a docstring, an instruction) is never
  scanned, and the tree's own corrected messages pass unchanged because they name the mtime fact, never an
  owner.

Scope is the reporting surface on purpose: a comment or docstring that *quotes* a forbidden phrase to
explain the rule is not blame a reader acts on, so it must not red. The guard closes the class — a future
reporting leg that reintroduces the guess without a sha reds `ci-unit`.

Commands:
    check_report_hygiene.py check     exit 1 on a blame sentence with no sha anchor, listing them
    check_report_hygiene.py report    show every reporting leg scanned and the verdict

Usage:
    python3 scripts/check_report_hygiene.py check
    python3 scripts/check_report_hygiene.py report
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = "scripts"
WORKFLOWS = ".github/workflows"

#: Ownership pronouns — naming WHOSE work the sentence attributes a change to.
OWNER = (r"another lane's|another lane|the other lane|a sibling lane|the sibling lane|"
         r"some other lane|a different lane|someone else|other lane|this lane's|this lane")
#: Adverse shared-state change verbs — the verbs that ATTRIBUTE who moved/changed shared work.
VERB = (r"advanced?|advancing|rewrote|rewritt\w*|overwrote?|overwritt\w*|pushed?|pushing|"
        r"edited?|editing|changed?|changing|updated?|moving|moved?|bumped?|deleted?|dropped?|"
        r"reverted?|modified?|touched?|went ahead|failed?|reddened?|broke?\b")
#: An evidence anchor — a named sha in any of the spellings the fleet uses.
SHA_ANCHOR = re.compile(r"(?:@|\$)[0-9a-f]{7,40}|[0-9a-f]{7,40}")
OWNER_RE = re.compile(rf"\b(?:{OWNER})\b", re.I)
VERB_RE = re.compile(rf"\b(?:{VERB})\b", re.I)
#: How far apart an owner pronoun and a change verb may be and still be one blame sentence.
WINDOW = 70


def _docstring_node(node) -> ast.Constant | None:
    """The docstring Constant of a module/function/class, or None (never scanned)."""
    body = getattr(node, "body", None)
    if isinstance(body, list) and body and isinstance(body[0], ast.Expr) \
            and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
        return body[0].value
    return None


def emitted_strings(text: str) -> list[tuple[int, str]]:
    """The (line, text) pairs a Python file EMITS: string constants and f-string literal fragments.

    Docstrings are excluded — they document a rule, they are not reporting output — and an f-string's
    literal fragments are joined (a blame sentence split by `{var}` is still read by a human as one
    sentence, but only the literal words are matched; a variable never fabricates a blame phrase).
    """
    tree = ast.parse(text)
    doc_ids = {id(_docstring_node(n)) for n in ast.walk(tree) if _docstring_node(n)}
    out: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in doc_ids:
            out.append((node.lineno, node.value))
        elif isinstance(node, ast.JoinedStr):
            parts = "".join(v.value for v in node.values
                            if isinstance(v, ast.Constant) and isinstance(v.value, str))
            if parts:
                out.append((node.lineno, parts))
    return out


def emitted_lines(text: str) -> list[tuple[int, str]]:
    """The (line, text) pairs a workflow EMITS: step `name:` and `run:` values."""
    return [(i, line) for i, line in enumerate(text.splitlines(), 1)
            if ("name:" in line or "run:" in line)]


def blame_sentence(text: str) -> bool:
    """Is `text` an ownership-guess blame sentence without an evidence anchor?

    True when an ownership pronoun and an adverse change verb sit within WINDOW of each other (either
    order — "another lane advanced it" and "the file was moved by another lane" are both blame) and the
    line carries no sha. A sha anchor anywhere on the line makes it evidence, not a guess.
    """
    if SHA_ANCHOR.search(text):
        return False
    owners = [m.start() for m in OWNER_RE.finditer(text)]
    verbs = [m.start() for m in VERB_RE.finditer(text)]
    if not owners or not verbs:
        return False
    for o in owners:
        for v in verbs:
            if abs(o - v) <= WINDOW:
                return True
    return False


def _reporting_legs(root: Path) -> list[tuple[str, int, str]]:
    """Every emitted reporting line across the tree: (path, line, text)."""
    out: list[tuple[str, int, str]] = []
    for path in sorted((root / SCRIPTS).glob("*.py")):
        rel = str(path.relative_to(root))
        try:
            for ln, s in emitted_strings(path.read_text()):
                out.append((rel, ln, s))
        except SyntaxError:
            out.append((rel, 0, ""))
    for path in sorted((root / WORKFLOWS).glob("*.yml")):
        rel = str(path.relative_to(root))
        for ln, s in emitted_lines(path.read_text()):
            out.append((rel, ln, s))
    return out


def findings(root: Path = REPO) -> list[dict]:
    """Every blame sentence without an evidence anchor that a reporting leg emits."""
    items: list[dict] = []
    for rel, ln, text in _reporting_legs(root):
        if not text.strip() or not blame_sentence(text):
            continue
        shown = " ".join(text.split())
        items.append({
            "key": f"ownership-guess/{rel}:{ln}",
            "title": f"report-hygiene: {rel}:{ln} blames ownership without an evidence sha",
            "where": f"{rel}:{ln}",
            "evidence": (
                f"`{shown[:200]}` attributes whose work did something but names no sha. A changed file "
                f"has no author-of-record in the commit graph, so an ownership claim is a guess unless a "
                f"specific `@<sha>` / `$<sha>` is anchored on the line. Name the evidence or stay silent "
                f"(issue #1292)."
            ),
        })
    return items


def render(items: list[dict]) -> str:
    if not items:
        return "[report-hygiene] OK: no reporting leg blames ownership without a sha evidence anchor"
    lines = [f"[report-hygiene] {len(items)} violation(s)"]
    for f in items:
        lines += ["", f"- {f['title']}", f"  where: {f['where']}", f"  {f['evidence']}"]
    return "\n".join(lines)


def report(root: Path = REPO) -> str:
    lines = ["[report-hygiene] reporting legs scanned (emitted strings + workflow name:/run: lines)"]
    for rel, ln, text in _reporting_legs(root):
        if text.strip():
            lines.append(f"- {rel}:{ln}  {blame_sentence(text)!s:5}  {text.strip()[:70]}")
    lines += ["", render(findings(root))]
    return "\n".join(lines)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="check_report_hygiene", description=__doc__)
    sub = p.add_subparsers(dest="cmd")
    for name in ("check", "report"):
        sub.add_parser(name).add_argument("--root", default=str(REPO))
    args = p.parse_args(argv)
    if not args.cmd:
        p.error("need a command: check | report")
    root = Path(args.root)
    if args.cmd == "report":
        print(report(root))
        return 0
    items = findings(root)
    print(render(items))
    return 1 if items else 0


if __name__ == "__main__":
    raise SystemExit(main())
