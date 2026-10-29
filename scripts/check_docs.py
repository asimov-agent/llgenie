#!/usr/bin/env python3
"""Is every user-facing make target documented, and is the README a user guide? (issue #257, #678)

`README.md` is the document a new user reads: what llgenie is, how to install it, how to use it,
and how it works, with links to `docs/ARCHITECTURE.md`, `docs/ENGINES.md`, `docs/BOTS.md` and
`CHANGES.md`. It is NOT a change log — a change's own record is a dated note in `agent-wiki/`,
indexed by `CHANGES.md` (issue #678). Nothing enforced either rule, so a target could ship
undocumented, and every landed change could (and did) append another issue-numbered section to the
README until it was 2,600 lines of work record.

  check_docs.py report    print every documented/undocumented target, the exceptions, each work
                          record's references, and the README/CHANGES verdict
  check_docs.py check     exit 1 on any defect below

What "documented" means — one definition, no guessing:

- a **documented target** is a make target that carries a `##` help line (the targets
  `make help` prints — the user-facing surface) AND is named in the **documentation surface**:
  `README.md` plus every markdown file under `docs/` that the README links to. A user target
  belongs in the README; an automation target belongs in `docs/BOTS.md`; both count;
- a target is matched **whole-token** (`docs-report` in the README does not document `docs`), and
  a **pattern target** (`build-engine-%`, `run-engine-%`) is documented by its stem;
- a target that is user-facing but deliberately documented nowhere must be recorded in
  `tests/fixtures/docs-exceptions.json` (reason + decided date + issue) — an omission is a dated
  decision, not an accident. A recorded exception that the surface now documents is STALE and must
  be deleted, so the file cannot rot;
- every `agent-wiki/*.md` entry must **reference** the issue or PR it implements (`#<n>`) — a work
  record that names no issue is unfalsifiable — and must be **indexed by one fragment** of its own
  under `docs/changes.d/` (one row per file, so no two changes edit one line — issue #934);
- every fragment must name the note of its own name and be one well-formed row, and `CHANGES.md`
  (rendered from the fragments by `make changes-index`) must link no note that is missing;
  `README.md` must link `CHANGES.md`;
- `README.md` must stay a user guide: no heading carrying an `(issue #N)` change reference, no
  generated dispatch-table marker, and no change-log heading — a bot that appends change history
  to it fails this gate instead of being able to.

Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MAKEFILE = "Makefile"
README = "README.md"
CHANGES = "CHANGES.md"
FRAGMENTS = "docs/changes.d"
DOCS_DIR = "docs"
WIKI_DIR = "agent-wiki"
EXCEPTIONS = "tests/fixtures/docs-exceptions.json"

# `target: ... ## help` — the shape `make help` prints (and so the user-facing surface).
TARGET_RE = re.compile(r"^([a-z0-9][a-z0-9._-]*%?):[^\n]*##[^\n]*$", re.M)
# An issue/PR reference in a work record: "#123", "issue 123", "PR 123", "issues #1, #2".
REF_RE = re.compile(r"#\d+|\b(?:issue|issues|pr|PRs?)\s+#?\d+", re.I)
# A README heading that is a change record, not a section of the user guide.
CHANGE_HEADING_RE = re.compile(r"^#{1,6} .*?\((?:issues?|prs?)\s*#?\d+", re.M | re.I)
# A change-log heading under any spelling a bot would append.
CHANGELOG_HEADING_RE = re.compile(r"^#{1,6}\s+(?:change\s?log|changelog|recent changes|changes)\s*$",
                                  re.M | re.I)
# A markdown link to a work record, as `CHANGES.md` writes them.
WIKI_LINK_RE = re.compile(r"\]\((?:\./)?agent-wiki/([^)\s]+\.md)\)")
# A markdown link the README uses to reach a reference document.
DOC_LINK_RE = re.compile(r"\]\((?:\./)?(docs/[^)\s]+\.md)\)")


def _targets(root: Path) -> dict[str, str]:
    """`{target: its help text}` for every target `make help` would print."""
    text = (root / MAKEFILE).read_text()
    out: dict[str, str] = {}
    for m in TARGET_RE.finditer(text):
        name = m.group(1)
        out.setdefault(name, m.group(0).split("##", 1)[1].strip())
    return out


def _stem(target: str) -> str:
    """A pattern target is documented by its stem (`run-engine-%` -> `run-engine`)."""
    return target.rstrip("%")


def _documents(readme: str, target: str) -> bool:
    """Whole-token match: `docs` is not documented by the word `docs-report`."""
    stem = _stem(target)
    return bool(re.search(r"(?<![A-Za-z0-9_-])" + re.escape(stem) + r"(?![A-Za-z0-9_-])", readme))


def _readme(root: Path) -> str:
    """The README's own text (empty when it does not exist — the caller reports that)."""
    path = root / README
    return path.read_text() if path.exists() else ""


def _surface(root: Path) -> dict[str, str]:
    """`{doc: text}` for the README and every `docs/` page it links to."""
    readme = _readme(root)
    docs: dict[str, str] = {README: readme}
    for rel in sorted(set(DOC_LINK_RE.findall(readme))):
        path = root / rel
        if path.exists():
            docs[rel] = path.read_text()
    return docs


def _exceptions(root: Path) -> dict:
    """The recorded user-facing targets that stay out of the docs, plus its metadata."""
    path = root / EXCEPTIONS
    if not path.exists():
        return {"path": str(path), "decided_utc": None, "targets": {}}
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        raise SystemExit(f"[check-docs] {path}: not valid JSON: {e}")
    targets = data.get("targets") or {}
    if not isinstance(targets, dict):
        raise SystemExit(f"[check-docs] {path}: 'targets' must be an object")
    for target, entry in targets.items():
        if not isinstance(entry, dict):
            raise SystemExit(f"[check-docs] {path}: {target!r} must be an object")
        for key in ("reason", "decided", "issue"):
            if not entry.get(key):
                raise SystemExit(f"[check-docs] {path}: {target!r} lacks {key!r}")
    return {"path": str(path), "decided_utc": data.get("decided_utc"), "targets": targets}


def _wiki_entries(root: Path) -> dict[str, str]:
    """`{entry name: text}` for every `agent-wiki/*.md` work record."""
    wiki = root / WIKI_DIR
    if not wiki.is_dir():
        return {}
    return {p.name: p.read_text() for p in sorted(wiki.glob("*.md"))}


def _index_fragments(root: Path) -> dict[str, str]:
    """`{note stem: fragment text}` for every `docs/changes.d/*.md` index row (issue #934)."""
    d = root / FRAGMENTS
    if not d.is_dir():
        return {}
    return {p.stem: p.read_text() for p in sorted(d.glob("*.md"))}


def _index_module():
    """`scripts/changes_index.py` — one parser for the index, shared with its own target."""
    if str(Path(__file__).resolve().parent) not in sys.path:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
    import changes_index as ci
    return ci


def graph(root: Path = REPO) -> dict:
    """The documentation graph, computed from the real files."""
    targets = _targets(root) if (root / MAKEFILE).exists() else {}
    surface = _surface(root)
    readme = surface.get(README, "")
    joined = "\n".join(surface.values())
    documented = [t for t in targets if _documents(joined, t)]
    undocumented = [t for t in targets if t not in documented]
    changes = (root / CHANGES).read_text() if (root / CHANGES).exists() else ""
    return {
        "root": str(root),
        "readme": README,
        "readme_text": readme,
        "surface": list(surface),
        "targets": targets,
        "documented": documented,
        "undocumented": undocumented,
        "exceptions": _exceptions(root),
        "wiki": {name[:-3]: text for name, text in _wiki_entries(root).items()},
        "fragments": _index_fragments(root),
        "changes": changes,
        "changes_links": sorted(set(WIKI_LINK_RE.findall(changes))),
        "change_headings": [m.group(0).strip() for m in CHANGE_HEADING_RE.finditer(readme)]
                            + [m.group(0).strip() for m in CHANGELOG_HEADING_RE.finditer(readme)],
    }


def problems(info: dict) -> list[str]:
    """Every documentation defect: an undocumented target, a stale/undocumented exception, a work
    record that references no issue or PR or is not indexed, a dangling index row, and a README
    that carries change history or does not reach the index."""
    recorded = info["exceptions"]["targets"]
    errors: list[str] = []
    for target in info["undocumented"]:
        if target in recorded:
            continue
        errors.append(
            f"`make {target}` is user-facing (it has a `##` help line) but is documented in neither "
            f"{info['readme']} nor {DOCS_DIR}/ — document it, or record it in {EXCEPTIONS} with a reason"
        )
    for target, entry in recorded.items():
        if target not in info["targets"]:
            errors.append(f"{EXCEPTIONS}: {target!r} is not a user-facing make target any more")
        elif target in info["documented"]:
            errors.append(
                f"{EXCEPTIONS}: {target!r} is STALE — the docs document it now; delete the entry"
            )
    for stem, text in info["wiki"].items():
        if not REF_RE.search(text):
            errors.append(f"{WIKI_DIR}/{stem}.md: references no issue or PR (`#<n>`)")
        if stem not in info["fragments"]:
            errors.append(
                f"{WIKI_DIR}/{stem}.md: is not indexed — add {FRAGMENTS}/{stem}.md with its row "
                f"(one change, one note, one index row of its own)"
            )
    ci = _index_module()
    for stem, text in info["fragments"].items():
        row, errs = ci.parse_row(text, stem)
        errors.extend(errs)
        if stem not in info["wiki"]:
            errors.append(
                f"{FRAGMENTS}/{stem}.md: links {WIKI_DIR}/{stem}.md, which does not exist"
            )
    known = {stem + ".md" for stem in info["wiki"]}
    for name in info["changes_links"]:
        if name not in known:
            errors.append(f"{CHANGES}: links {WIKI_DIR}/{name}, which does not exist")
    if not info["changes"]:
        errors.append(f"{CHANGES} does not exist — it is the index of the {WIKI_DIR}/ work records")
    elif not re.search(r"\]\((?:\./)?CHANGES\.md\)", info["readme_text"]):
        errors.append(f"{info['readme']} does not link {CHANGES}, so a reader never finds the records")
    for heading in info["change_headings"]:
        errors.append(
            f"{info['readme']}: {heading!r} is change history, not a user-guide section — the change "
            f"belongs in its {WIKI_DIR}/ note, indexed by {CHANGES}"
        )
    if "<!-- dispatch-forms:" in info["readme_text"]:
        errors.append(
            f"{info['readme']} carries a generated dispatch table — it lives in {DOCS_DIR}/BOTS.md, "
            f"so no bot regenerates the README"
        )
    return errors


def report(info: dict) -> str:
    recorded = info["exceptions"]["targets"]
    lines = [
        f"[check-docs] {info['root']}",
        f"[check-docs] {len(info['targets'])} user-facing (## help) make targets, "
        f"{len(info['documented'])} documented in {len(info['surface'])} doc(s) "
        f"({', '.join(info['surface'])}), {len(info['undocumented'])} not, "
        f"{len(recorded)} recorded exception(s)",
    ]
    for target in info["undocumented"]:
        mark = "recorded" if target in recorded else "MISSING"
        lines.append(f"[check-docs]   {mark:8} make {target}")
    for target, entry in sorted(recorded.items()):
        lines.append(
            f"[check-docs]   exception {target} (issue #{entry['issue']}, {entry['decided']}): "
            f"{entry['reason']}"
        )
    for stem, text in info["wiki"].items():
        refs = REF_RE.findall(text)
        indexed = "indexed" if stem in info["fragments"] else "NOT INDEXED"
        if refs:
            lines.append(f"[check-docs]   {WIKI_DIR}/{stem}.md: {len(refs)} issue/PR reference(s), {indexed}")
        else:
            lines.append(f"[check-docs]   {WIKI_DIR}/{stem}.md: NO issue/PR reference")
    lines.append(
        f"[check-docs] {FRAGMENTS}: {len(info['fragments'])} index row(s); "
        f"{CHANGES}: {len(info['changes_links'])} note link(s); "
        f"{len(info['change_headings'])} change-history heading(s) in {info['readme']}"
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="check_docs.py", description=__doc__)
    parser.add_argument("mode", choices=("check", "report"))
    parser.add_argument("--root", default=str(REPO),
                        help="checkout to check (default: this file's repo; a test seam)")
    args = parser.parse_args(argv)
    info = graph(Path(args.root))
    if args.mode == "report":
        print(report(info))
        return 0
    errors = problems(info)
    for err in errors:
        print(f"[check-docs] ERROR: {err}", file=sys.stderr)
    if errors:
        print(f"[check-docs] {len(errors)} problem(s); see `make docs-report`", file=sys.stderr)
        return 1
    print(
        f"[check-docs] ok: every one of the {len(info['targets'])} user-facing make targets is "
        f"documented in {len(info['surface'])} doc(s) (or a recorded exception), every "
        f"{len(info['wiki'])} {WIKI_DIR}/ entry references an issue or PR and has its own index "
        f"row in {FRAGMENTS}, {CHANGES} links no missing note, and {info['readme']} carries no "
        f"change history"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
