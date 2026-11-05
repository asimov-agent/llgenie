#!/usr/bin/env python3
"""A reporting leg emits the FULL status header or stays silent about state (issue #1615).

The fleet report contract demands every report open with the six-field header:
`BOT <name> · working on #<id> · branch <ref> · since <hh:mmZ> · blocked on <x|none> · next <y>`,
and a report without an id, a branch or a run id is not a report. The id, branch and since fields
are the same-pass evidence the issue is about: a stale self-report is exactly a header that carries
fewer fields than the contract — it asserts state ("working on #5", "branch hotfix") without the
evidence that ties it to a same-pass measure. `check_report_hygiene` (#1292) already refuses
ownership-blame without a sha; this guard makes the header itself structural:

- it scans the tree's **reporting legs** — the strings a `scripts/*.py` actually *emits* (string
  constants and f-string literal fragments, excluding docstrings), plus workflow step
  `name:`/`run:` lines in `.github/workflows/*.yml`;
- a reporting string that carries a **header signal** — a bare `BOT <name>` line, or a `working on
  #<id>` fragment, or any of the field keywords (branch/since/blocked/next) used in a status line —
  must carry the **full six-field grammar**, one `·`-separated field per position;
- the sentence is a **violation** if any of the six required fields is absent. A line with no
  header signal is never scanned (a docstring explaining the rule, a comment, a plain echo).
  Fields with `<...>` placeholders in a rule statement satisfy nothing — a rule that *describes* a
  header is not a report, so it must not be counted as one either.

Scope is the reporting surface on purpose: a comment or docstring that *quotes* the header to
explain the rule is not a report a reader acts on, so it cannot red. The guard closes the class —
a future reporting leg that emits a partial status header reds `ci-unit`.

Commands:
    check_report_header.py check     exit 1 on an emitted header with a missing field, listing them
    check_report_header.py report    show every reporting leg scanned and the verdict

Usage:
    python3 scripts/check_report_header.py check
    python3 scripts/check_report_header.py report
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

#: The six required fields, in order, each as the literal text that must appear (with its value).
FIELDS = ("BOT", "working on #", "branch ", "since ", "blocked on ", "next ")
SEPARATOR = "·"

#: The full contract, as a single constant INTERPOLATED (never split into scan-visible header
#: literals) into every emitted message — a rule teaching the grammar, not a report asserting one.
CONTRACT = "BOT <name> · working on #<id> · branch <ref> · since <hh:mmZ> · blocked on <x|none> · next <y>"

#: A line whose value resolves a field (a `#<id>`/`<ref>`/`<hh:mmZ>` placeholder resolves nothing).
PLACEHOLDER_TEMPLATE = re.compile(r"#<[A-Za-z]+>|<[A-Za-z:]+>|<[a-z|]+>")


def _docstring_node(node) -> ast.Constant | None:
    """The docstring Constant of a module/function/class, or None (never scanned)."""
    body = getattr(node, "body", None)
    if isinstance(body, list) and body and isinstance(body[0], ast.Expr) \
            and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
        return body[0].value
    return None


def emitted_strings(text: str) -> list[tuple[int, str]]:
    """The (line, text) pairs a Python file EMITS: string constants and f-string literal fragments.

    Docstrings are excluded — they document a rule, they are not reporting output — and an
    f-string's literal fragments are joined (a header split by `{var}` is still read by a human as
    one status line, but only the literal words are matched; a variable never fabricates a field).
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


def _resolves(segment: str, field: str) -> bool:
    """Does `segment` STATE `field` with a value, not a template placeholder?

    A rule statement that says `working on #<id>` describes the header for teaching; it does not
    assert a same-pass id, so it must not be accepted as evidence on a reporting surface. A real
    report says `working on #1615` (resolves) or `blocked on none` / `next merge` (concrete).
    """
    if PLACEHOLDER_TEMPLATE.search(segment):
        return False
    return field in segment or segment.strip().startswith(field.strip())


def _is_full_template_quote(text: str) -> bool:
    """Is `text` the RULE, not a report — the whole header with every value a `<...>` placeholder?

    A reporting surface that quotes the contract as a template (`BOT <name> · working on #<id> ·
    branch <ref> · since <hh:mmZ> · blocked on <x|none> · next <y>` — every field a placeholder,
    no concrete value resolves) is teaching the rule, not asserting a same-pass state. It must not
    be scanned as a report, and must not red.
    """
    if SEPARATOR not in text:
        return False
    # every one of the six fields appears AND carries only a placeholder value
    for field in FIELDS:
        if field not in text:
            return False
    segments = [seg.strip() for seg in text.split(SEPARATOR)]
    concrete = any(PLACEHOLDER_TEMPLATE.search(seg) is None
                   and any(f in seg for f in FIELDS) and not seg.strip().startswith("BOT")
                   for seg in segments)
    return not concrete


def header_signal(text: str) -> bool:
    """Is `text` a reporting leg that CLAIMS to be a status header?

    Signals: a `working on #<id>` fragment, or a `·`-separated status line that pairs a BOT marker
    with at least two of the field keywords. A bare `BOT` (a config variable), a story prefixed
    `BOT — ` with em-dashes (prose, not a `·` header), and a plain comment/echo are not signals
    and are never scanned. A full placeholder template that only teaches the rule is not a signal
    either (a rule has no same-pass state to assert).
    """
    stripped = text.strip()
    if not stripped or _is_full_template_quote(stripped):
        return False
    # a REAL report id is concrete (`working on #1615`); a bare `working on #` (a keyword
    # constant) or `working on #<id>` (a template) resolves no same-pass id — not a signal.
    if re.search(r"working on #[0-9a-zA-Z]", stripped):
        return True
    if SEPARATOR in stripped and re.search(r"\bBOT\b", stripped):
        named = sum(1 for f in FIELDS if f in text)
        return named >= 2
    return False


def header_violation(text: str) -> list[str]:
    """The fields a header-signal line is missing, or an empty list when it is complete.

    An emitted header must state all six fields with real values, in position. A partial header
    is the stale-self-report the contract refuses — a report without an id, a branch or a run id
    is not a report.
    """
    if not header_signal(text):
        return []
    missing = []
    for field in FIELDS:
        # each field must appear in its position; `working on #` must also carry a concrete id
        if field not in text:
            missing.append(field)
            continue
        # a `working on #<id>` template placeholder, or a bare-keyword with a placeholder value,
        # resolves nothing — refuse it just as the contract refuses a missing field.
        if not _resolves(text, field):
            missing.append(field)
    return missing


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
    """Every reporting leg that emits a status header missing one or more of the six fields."""
    items: list[dict] = []
    for rel, ln, text in _reporting_legs(root):
        if not text.strip():
            continue
        missing = header_violation(text)
        if not missing:
            continue
        shown = " ".join(text.split())
        items.append({
            "key": f"partial-header/{rel}:{ln}",
            "title": f"report-header: {rel}:{ln} emits a status header missing {', '.join(missing)}",
            "where": f"{rel}:{ln}",
            "evidence": (
                f"`{shown[:200]}` carries a header signal but not the full six-field contract "
                f"{CONTRACT!r}. A report without an id, a branch or a run id is "
                f"not a report — emit the full status header or stay silent (issue #1615)."
            ),
        })
    return items


def render(items: list[dict]) -> str:
    if not items:
        return "[report-header] OK: no reporting leg emits a status header missing a field"
    lines = [f"[report-header] {len(items)} violation(s)"]
    for f in items:
        lines += ["", f"- {f['title']}", f"  where: {f['where']}", f"  {f['evidence']}"]
    return "\n".join(lines)


def report(root: Path = REPO) -> str:
    lines = ["[report-header] reporting legs scanned (emitted strings + workflow name:/run: lines)"]
    for rel, ln, text in _reporting_legs(root):
        if text.strip():
            lines.append(f"- {rel}:{ln}  {header_violation(text)!s:5}  {text.strip()[:70]}")
    lines += ["", render(findings(root))]
    return "\n".join(lines)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="check_report_header", description=__doc__)
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
