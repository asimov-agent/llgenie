#!/usr/bin/env python3
"""Is every user-facing make target documented in README.md? (issue #257)

AGENTS.md: "Any change that adds, renames, or alters a user-facing feature, `make`
command, target, or workflow MUST be mirrored in `README.md` in the same change" and
"Track progress in `agent-wiki/`". Nothing enforced either, so a target could be
added, shipped and never appear in the README the user reads, and a work record could
name no issue or PR at all. This is that rule, computed from the real files:

  check_docs.py report    print every documented/undocumented target, and the exceptions
  check_docs.py check     exit 1 on an undocumented target, a stale exception, a
                          malformed exception, or an agent-wiki entry with no issue/PR

What "documented" means — one definition, no guessing:

- a **documented target** is a make target that carries a `##` help line (the targets
  `make help` prints — the user-facing surface) AND is named in `README.md`;
- a target is matched **whole-token** in the README (`docs-report` in the README does
  not document `docs`), and a **pattern target** (`build-engine-%`, `run-engine-%`) is
  documented by its stem (`build-engine`, `run-engine`);
- a target that is user-facing but deliberately not in the README must be recorded in
  `tests/fixtures/docs-exceptions.json` (reason + decided date + issue) — an omission
  is a dated decision, not an accident. A recorded exception that the README now
  documents is STALE and must be deleted, so the file cannot rot;
- every `agent-wiki/*.md` entry must **reference** the issue or PR it implements
  (`#<n>`) — a work record that names no issue is unfalsifiable.

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
WIKI_DIR = "agent-wiki"
EXCEPTIONS = "tests/fixtures/docs-exceptions.json"

# `target: ... ## help` — the shape `make help` prints (and so the user-facing surface).
TARGET_RE = re.compile(r"^([a-z0-9][a-z0-9._-]*%?):[^\n]*##[^\n]*$", re.M)
# An issue/PR reference in a work record: "#123", "issue 123", "PR 123", "issues #1, #2".
REF_RE = re.compile(r"#\d+|\b(?:issue|issues|pr|PRs?)\s+#?\d+", re.I)


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


def _exceptions(root: Path) -> dict:
    """The recorded user-facing targets that stay out of the README, plus its metadata."""
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


def graph(root: Path = REPO) -> dict:
    """The documentation graph, computed from the real files."""
    targets = _targets(root) if (root / MAKEFILE).exists() else {}
    readme = (root / README).read_text() if (root / README).exists() else ""
    documented = [t for t in targets if _documents(readme, t)]
    undocumented = [t for t in targets if t not in documented]
    return {
        "root": str(root),
        "readme": README,
        "targets": targets,
        "documented": documented,
        "undocumented": undocumented,
        "exceptions": _exceptions(root),
        "wiki": _wiki_entries(root),
    }


def problems(info: dict) -> list[str]:
    """Errors: an undocumented user-facing target, a stale/undocumented exception, a
    work record that references no issue or PR."""
    recorded = info["exceptions"]["targets"]
    what = info["readme"]
    errors: list[str] = []
    for target in info["undocumented"]:
        if target in recorded:
            continue
        errors.append(
            f"{what}: `make {target}` is user-facing (it has a `##` help line) but is not "
            f"documented there — document it, or record it in {EXCEPTIONS} with a reason"
        )
    for target, entry in recorded.items():
        if target not in info["targets"]:
            errors.append(f"{EXCEPTIONS}: {target!r} is not a user-facing make target any more")
        elif target in info["documented"]:
            errors.append(
                f"{EXCEPTIONS}: {target!r} is STALE — {what} documents it now; delete the entry"
            )
    for name, text in info["wiki"].items():
        if not REF_RE.search(text):
            errors.append(f"{WIKI_DIR}/{name}: references no issue or PR (`#<n>`)")
    return errors


def report(info: dict) -> str:
    recorded = info["exceptions"]["targets"]
    lines = [
        f"[check-docs] {info['root']}",
        f"[check-docs] {len(info['targets'])} user-facing (## help) make targets, "
        f"{len(info['documented'])} documented in {info['readme']}, "
        f"{len(info['undocumented'])} not, {len(recorded)} recorded exception(s)",
    ]
    for target in info["undocumented"]:
        mark = "recorded" if target in recorded else "MISSING"
        lines.append(f"[check-docs]   {mark:8} make {target}")
    for target, entry in sorted(recorded.items()):
        lines.append(
            f"[check-docs]   exception {target} (issue #{entry['issue']}, {entry['decided']}): "
            f"{entry['reason']}"
        )
    for name, text in info["wiki"].items():
        refs = REF_RE.findall(text)
        lines.append(
            f"[check-docs]   {WIKI_DIR}/{name}: {len(refs)} issue/PR reference(s)"
            if refs else f"[check-docs]   {WIKI_DIR}/{name}: NO issue/PR reference"
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
        f"documented in {info['readme']} (or a recorded exception), and every "
        f"{len(info['wiki'])} {WIKI_DIR}/ entry references an issue or PR"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
