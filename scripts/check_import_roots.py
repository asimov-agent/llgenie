#!/usr/bin/env python3
"""One import root for the test suite (issue #796): a guard that refuses the two shapes that broke it.

The tests reach `scripts/` through `sys.path.insert` — 104 files did at `0ddfda8`, in seven distinct
shapes — so every test file carries its own bootstrap and the suite has as many import roots as files.
A migration to one root is only safe if the *absence* of the old shapes is checkable, and it is not
checkable by counting: a file that adds a path entry and then imports nothing from it looks migrated.
This guard is that check, and it is deliberately narrow — two rules, both about shapes that cannot be
made to work by any ordering of edits:

    sys-path  a `sys.path.insert` / `sys.path.append` outside `tests/conftest.py`
    bare      `import <name>` / `from <name> import …` where `<name>` is a module that lives in `scripts/`

Both are refusals, not warnings. `--allow` takes a path prefix that is exempt (the conftest, and a
deliberate exception recorded with its reason in the same list), so the list is the record of every
exception rather than a comment somewhere.

Usage:
    python3 scripts/check_import_roots.py check      # exit 1 on any finding
    python3 scripts/check_import_roots.py report     # the findings, or the two rules and their counts
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

#: The one file allowed to put `scripts/` on `sys.path`, because it is the seam every test inherits.
ALLOWED = ("tests/conftest.py",)

#: `sys.path.insert(...)` / `sys.path.append(...)`, including the aliased-module spellings.
SYS_PATH = re.compile(r"\bsys\.path\.(?:insert|append)\s*\(")

#: The recorded counts the guard ratchets against. Landing a guard on a tree that already violates it
#: 245 times means either a red gate or no gate; the baseline makes it a ratchet instead — the count may
#: fall (the migration batches) and may never rise (a new file adding its own root is refused at once).
BASELINE = Path("tests/fixtures/import-roots-baseline.json")

#: A top-level import statement, for the bare-import rule.
IMPORT_LINE = re.compile(r"^(?:import\s+([A-Za-z_][\w.]*)|from\s+([A-Za-z_][\w.]*)\s+import\b)", re.M)


def script_modules(root: Path) -> set[str]:
    """The importable module names `scripts/` provides — the set a bare import must not name."""
    return {p.stem for p in (root / "scripts").glob("*.py") if p.stem != "__init__"}


def test_files(root: Path) -> list[Path]:
    return sorted((root / "tests").rglob("*.py"))


def _allowed(rel: str, allow: tuple[str, ...]) -> bool:
    return any(rel == a or rel.startswith(a.rstrip("/") + "/") for a in allow)


def findings(root: Path = REPO_ROOT, allow: tuple[str, ...] = ALLOWED) -> list[dict]:
    """Every way a test file can carry its own import root, or import a `scripts/` module bare."""
    items: list[dict] = []
    modules = script_modules(root)
    for path in test_files(root):
        rel = str(path.relative_to(root))
        if _allowed(rel, allow):
            continue
        text = path.read_text()
        try:
            tree = ast.parse(text)
        except SyntaxError as exc:                      # a file that will not parse is its own finding
            items.append({"key": "syntax", "where": rel, "detail": f"does not parse: {exc.msg}"})
            continue
        # MODULE-LEVEL only. An insert inside a test body is a different animal: it points at a
        # temporary plugin tree the test just built (`sys.path.insert(0, str(home / "plugins" / "nerve"))`)
        # and removing it breaks the test rather than the seam. The rule is about the bootstrap.
        for node in tree.body:
            if not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Call):
                continue
            call = node.value
            if not (isinstance(call.func, ast.Attribute) and call.func.attr in ("insert", "append")):
                continue
            owner = call.func.value
            if not (isinstance(owner, ast.Attribute) and owner.attr == "path"
                    and isinstance(owner.value, ast.Name) and owner.value.id == "sys"):
                continue
            items.append({
                "key": "sys-path",
                "where": f"{rel}:{node.lineno}",
                "detail": "a module-level path entry outside tests/conftest.py: the suite is meant to "
                          "have one import root, and a per-file bootstrap is the shape that gave it "
                          "104 (issue #796)",
            })
            break                                       # one finding per file is enough to fix it
        for node in tree.body:                          # top-level imports only: a nested one is local
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module.split(".")[0]]
            for name in names:
                if name in modules:
                    items.append({
                        "key": "bare",
                        "where": f"{rel}:{node.lineno}",
                        "detail": f"`{name}` is a scripts/ module imported bare — import it as "
                                  f"`scripts.{name}` so one root resolves it (issue #796)",
                    })
    return items


def counts(root: Path = REPO_ROOT) -> dict[str, int]:
    items = findings(root)
    out = {"sys-path": 0, "bare": 0, "syntax": 0}
    for it in items:
        out[it["key"]] = out.get(it["key"], 0) + 1
    return out


def ratchet(root: Path = REPO_ROOT, allow: tuple[str, ...] = ALLOWED) -> list[dict]:
    """Findings that push a count above the recorded baseline — the only ones a landed guard can red on."""
    path = root / BASELINE
    now = counts(root)
    if not path.exists():
        return [{"key": "baseline", "where": str(BASELINE),
                 "detail": f"missing; record the current counts with `--update` ({now})"}]
    recorded = json.loads(path.read_text())
    items: list[dict] = []
    for key, value in sorted(now.items()):
        was = int(recorded.get(key, 0))
        if value > was:
            items.append({
                "key": key,
                "where": str(BASELINE),
                "detail": f"{key}: {value} now, {was} recorded — the migration may only shrink this "
                          f"count (issue #796); a new file adding its own root is refused here",
            })
    return items


def update_baseline(root: Path = REPO_ROOT) -> Path:
    path = root / BASELINE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(counts(root), indent=2, sort_keys=True) + "\n")
    return path


def render(items: list[dict]) -> str:
    if not items:
        return "[import-roots] OK: no test file carries its own path entry, and no scripts/ module is imported bare"
    lines = [f"[import-roots] {len(items)} finding(s):"]
    lines += [f"  {it['where']}: {it['detail']}" for it in items]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="check_import_roots", description=__doc__)
    p.add_argument("cmd", choices=("check", "report", "ratchet"))
    p.add_argument("--root", default=str(REPO_ROOT))
    p.add_argument("--update", action="store_true", help="record the current counts as the baseline")
    p.add_argument("--allow", nargs="*", default=list(ALLOWED),
                   help="path prefixes exempt from both rules (default: tests/conftest.py)")
    args = p.parse_args(argv)
    root = Path(args.root).resolve()
    if args.update:
        path = update_baseline(root)
        print(f"[import-roots] baseline recorded: {path} {counts(root)}")
        return 0
    if args.cmd == "ratchet":
        items = ratchet(root, tuple(args.allow))
        print(render(items) if items else
              f"[import-roots] OK: counts at or below the recorded baseline {counts(root)}",
              file=sys.stderr if items else sys.stdout)
        return 1 if items else 0
    items = findings(root, tuple(args.allow))
    if args.cmd == "report":
        print(render(items))
        print(f"[import-roots] counts: {counts(root)}")
        return 0
    print(render(items), file=sys.stdout if not items else sys.stderr)
    return 1 if items else 0


if __name__ == "__main__":
    raise SystemExit(main())
