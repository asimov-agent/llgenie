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

The ratchet: `tests/fixtures/import-roots-baseline.json` records each rule's counted sites, `check`
fails when they RISE, and a batch that converts files lowers them — so the guard is green on today's
tree and still refuses tomorrow's new offender. **A baseline is a MEASUREMENT, not a constant.** It was
`34 bare / 14 sys-path` when this branch was cut and `107 / 151` on `main` a day later, because other
lanes added tests that bootstrap their own path; recorded as-is, the guard would have been red on
`main` itself. Re-record at what the branch actually produces (`--root <exported tree> report` measures
any tree without touching it) and the meaning is preserved — it may fall, never rise. A baseline copied
from an old cut asserts the past, and a guard that asserts the past is a guard people disable.

The baseline is SET-shaped: each rule records `{"count": N, "sites": ["tests/…:line", …]}`. The ratchet
diffs the sets, so a red names the ONE new `file:line` (a site present now and absent at the baseline)
instead of listing every site the rule counted and making the reader diff it (issue #1101). A site
recorded then and gone now is the reported shrink — allowed, because the migration may only shrink
(issue #796).

Usage:
    python3 scripts/check_import_roots.py check      # exit 1 on any finding
    python3 scripts/check_import_roots.py report     # the findings, or the two rules and their counts
    python3 scripts/check_import_roots.py ratchet    # exit 1 when a count rose, naming the sites it counted
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


def sites_by_rule(root: Path = REPO_ROOT, allow: tuple[str, ...] = ALLOWED) -> dict[str, set[str]]:
    """Every finding's `file:line` grouped by rule — the set the set-shaped baseline records."""
    out: dict[str, set[str]] = {}
    for it in findings(root, allow):
        out.setdefault(it["key"], set()).add(it["where"])
    return out


def counts(root: Path = REPO_ROOT, allow: tuple[str, ...] = ALLOWED) -> dict[str, int]:
    items = findings(root, allow)
    out = {"sys-path": 0, "bare": 0, "syntax": 0}
    for it in items:
        out[it["key"]] = out.get(it["key"], 0) + 1
    return out


def ratchet(root: Path = REPO_ROOT, allow: tuple[str, ...] = ALLOWED) -> list[dict]:
    """Refusals that push a rule past its recorded baseline — the only ones a landed guard can red on.

    Set-shaped (issue #1101): the baseline records each rule's counted `file:line` sites, so the
    refusal is a genuine set difference — a site present now and absent at the baseline is the ONE new
    root, named exactly (issue #1066 could only list every site and let the reader diff). A site
    recorded then and gone now is the reported, allowed shrink (issue #796). A legacy count-shaped
    baseline entry (a plain number, the pre-#1101 shape) still ratchets by count and names all its
    sites, with a note to re-record once with `--update`.
    """
    path = root / BASELINE
    now = sites_by_rule(root, allow)
    if not path.exists():
        return [{"key": "baseline", "where": str(BASELINE), "missing": True,
                 "detail": f"missing; record the current sites with `--update` "
                           f"({{k: len(v) for k, v in now.items()}})"}]
    recorded = json.loads(path.read_text())
    items: list[dict] = []
    for key in sorted(set(recorded) | set(now)):
        rec = recorded.get(key)
        cur = now.get(key, set())
        if isinstance(rec, (int, float)) or rec is None:   # legacy count-shaped entry
            was = int(rec or 0)
            if len(cur) > was:
                items.append({"key": key, "where": str(BASELINE), "legacy": True,
                              "now": len(cur), "was": was, "new": sorted(cur),
                              "detail": f"{key}: {len(cur)} now, {was} recorded — this baseline "
                                        f"entry is count-shaped; re-record once with `--update` so a "
                                        f"red names the new file (issue #1101)"})
            continue
        rec_sites = set(rec.get("sites", []))
        was = int(rec.get("count", len(rec_sites)))
        new = sorted(cur - rec_sites)
        removed = sorted(rec_sites - cur)
        if new:
            items.append({"key": key, "where": str(BASELINE), "new": new,
                          "now": len(cur), "was": was,
                          "detail": f"{key}: a NEW import root is refused — this exactly (issue #1101):"})
        if removed:
            items.append({"key": key, "removed": removed,
                          "detail": f"{key}: removed site(s), allowed — the migration may only shrink "
                                    f"(issue #796):"})
    return items


def update_baseline(root: Path = REPO_ROOT, allow: tuple[str, ...] = ALLOWED) -> Path:
    path = root / BASELINE
    path.parent.mkdir(parents=True, exist_ok=True)
    now = sites_by_rule(root, allow)
    data = {k: {"count": len(v), "sites": sorted(v)} for k, v in sorted(now.items())}
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    return path


def render(items: list[dict]) -> str:
    if not items:
        return "[import-roots] OK: no test file carries its own path entry, and no scripts/ module is imported bare"
    lines = [f"[import-roots] {len(items)} finding(s):"]
    lines += [f"  {it['where']}: {it['detail']}" for it in items]
    return "\n".join(lines)


def render_ratchet(items: list[dict]) -> str:
    """The refusal (a new site named exactly), the allowed shrink, and a legacy-baseline note.

    Issue #1101: a site present now and absent at the baseline is named exactly, the one new root
    (#1066 could only list every site the rule counted and let the reader diff).
    """
    lines: list[str] = []
    for it in items:
        if it.get("missing"):
            lines.append(f"[import-roots] {it['where']}: {it['detail']}")
            continue
        if it.get("legacy"):
            lines.append(f"[import-roots] {it['detail']}")
            for site in it.get("new") or []:
                lines.append(f"  {site}")
            continue
        if it.get("new"):
            lines.append(f"[import-roots] {it['detail']}  ({it['now']} now, {it['was']} recorded)")
            for site in it["new"]:
                lines.append(f"  {site}")
            continue
        if it.get("removed"):
            lines.append(f"[import-roots] {it['detail']}")
            for site in it["removed"]:
                lines.append(f"  {site}")
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
        refused = [it for it in items if it.get("new") or it.get("legacy")]
        print(render_ratchet(items) if items else
              f"[import-roots] OK: counts at or below the recorded baseline {counts(root)}",
              file=sys.stderr if refused else sys.stdout)
        return 1 if refused else 0
    items = findings(root, tuple(args.allow))
    if args.cmd == "report":
        print(render(items))
        print(f"[import-roots] counts: {counts(root)}")
        return 0
    print(render(items), file=sys.stdout if not items else sys.stderr)
    return 1 if items else 0


if __name__ == "__main__":
    raise SystemExit(main())
