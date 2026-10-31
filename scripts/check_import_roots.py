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

The ratchet: `tests/fixtures/import-roots-baseline.json` records the counts, `check` fails when they
RISE, and a batch that converts files lowers them — so the guard is green on today's tree and still
refuses tomorrow's new offender. **A baseline is a MEASUREMENT, not a constant.** It was `34 bare /
14 sys-path` when this branch was cut and `107 / 151` on `main` a day later, because other lanes added
tests that bootstrap their own path; recorded as-is, the guard would have been red on `main` itself.
Re-record at what the branch actually produces (`--root <exported tree> report` measures any tree
without touching it) and the meaning is preserved — it may fall, never rise. A baseline copied from an
old cut asserts the past, and a guard that asserts the past is a guard people disable.

Usage:
    python3 scripts/check_import_roots.py check      # exit 1 on any finding
    python3 scripts/check_import_roots.py report     # the findings, or the two rules and their counts
    python3 scripts/check_import_roots.py ratchet    # exit 1 when a NEW site crosses the recorded set
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

#: The recorded baseline the guard ratchets against. Landing a guard on a tree that already violates it
#: 245 times means either a red gate or no gate; the baseline makes it a ratchet instead — the count may
#: fall (the migration batches) and may never rise (a new file adding its own root is refused at once).
#: The baseline is SET-shaped (issue #1101): `{"bare": {"count": 52, "sites": ["tests/a.py:12", ...]}, ...}`
#: so the ratchet can tell the NEW site from the pre-existing ones — the aggregate says the count rose,
#: the `sites` list says which one (a number alone cannot; issue #1101). An older count-shaped record
#: (`{"bare": 52}`) still loads, at the cost of naming every site (the pre-#1101 behaviour), so the
#: transition needs no forced re-record.
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


def _load_baseline(recorded: dict) -> dict[str, dict]:
    """Normalise a recorded baseline into `key -> {"shape": str, "count": int, "sites": frozenset[str]}`.

    Accepts the set-shaped record (#1101: `{"bare": {"count": 52, "sites": [...]}}`) and the old
    count-shaped record (`{"bare": 52}`). A count-shaped value carries `shape="count"` and an empty
    site set, which keeps the pre-#1101 comparison (count rise, name every site); a set-shaped value
    carries `shape="set"` so the ratchet can refuse on the true set difference.
    """
    out: dict[str, dict] = {}
    for key, value in recorded.items():
        if isinstance(value, dict):
            out[key] = {"shape": "set",
                        "count": int(value.get("count", 0)),
                        "sites": frozenset(value.get("sites", []))}
        else:
            out[key] = {"shape": "count", "count": int(value), "sites": frozenset()}
    return out


def ratchet_delta(root: Path = REPO_ROOT, allow: tuple[str, ...] = ALLOWED) -> tuple[list[dict], list[dict]]:
    """The ratchet as a genuine SET difference (issue #1101), split into refusals and shrinks.

    Returns `(refused, shrunk)` where the baseline records a site set. A site present now but not in the
    baseline is a NEW site and a refusal, named precisely (not a list of every counted site); a site in
    the baseline but absent now is a sanctioned shrink (the migration that #796 allows) reported without
    failing. When the baseline is count-shaped (no site set) the whole current set is "new" — matching
    the pre-#1101 behaviour of naming every counted site.
    """
    now = counts(root)
    sites: dict[str, list[str]] = {}
    for finding in findings(root, allow):
        sites.setdefault(finding["key"], []).append(finding["where"])
    refused: list[dict] = []
    shrunk: list[dict] = []
    for key, value in sorted(now.items()):
        recorded = json.loads((root / BASELINE).read_text()) if (root / BASELINE).exists() else {}
        base = _load_baseline(recorded).get(key, {"shape": "count", "count": 0,
                                                  "sites": frozenset()})
        was_count = base["count"]
        nowset = frozenset(sites.get(key, []))
        if base["shape"] == "set":
            new_sites = nowset - base["sites"]
            removed = base["sites"] - nowset
            if new_sites:
                refused.append({
                    "key": key, "where": str(BASELINE), "shape": "set", "now": value, "was": was_count,
                    "over": len(new_sites), "new": sorted(new_sites), "removed": sorted(removed),
                    "detail": f"{key}: {value} now, {was_count} recorded — the migration may only "
                              f"shrink this count (issue #796); a new file adding its own root is "
                              f"refused here",
                })
            elif removed:
                shrunk.append({
                    "key": key, "where": str(BASELINE), "now": value, "was": was_count,
                    "removed": sorted(removed),
                    "detail": f"{key}: {value} now, {was_count} recorded — a root was removed, the "
                              f"sanctioned shrink (#796)",
                })
        elif value > was_count:                        # count-shaped baseline: the pre-#1101 rule
            refused.append({
                "key": key, "where": str(BASELINE), "shape": "count", "now": value, "was": was_count,
                "over": value - was_count, "new": sorted(nowset), "removed": [],
                "detail": f"{key}: {value} now, {was_count} recorded — the migration may only shrink "
                          f"this count (issue #796); a new file adding its own root is refused here",
            })
    return refused, shrunk


def ratchet(root: Path = REPO_ROOT, allow: tuple[str, ...] = ALLOWED) -> list[dict]:
    """Findings that push a count above the recorded baseline — the only ones a landed guard can red on.

    Each refusal names the `file:line` of the NEW site(s) that crossed the recorded set (`new`), so a
    reader never has to run `report` or diff the branch to find the offending file (issue #1066/#1101).
    Removals (the #796 migration) are reported via `ratchet_delta` without failing this gate.
    """
    path = root / BASELINE
    if not path.exists():
        now = counts(root)
        return [{"key": "baseline", "where": str(BASELINE),
                 "detail": f"missing; record the current counts with `--update` ({now})"}]
    refused, _ = ratchet_delta(root, allow)
    return refused


def update_baseline(root: Path = REPO_ROOT) -> Path:
    """Record a SET-shaped baseline (issue #1101): each rule's count and the site list it counted.

    The `sites` list is the same `file:line` set `report` prints for each rule, so the recorded baseline
    is the exact set the ratchet compares future trees against — a new site is a refusal, a removed site
    is the sanctioned shrink.
    """
    sites: dict[str, list[str]] = {}
    for finding in findings(root):
        sites.setdefault(finding["key"], []).append(finding["where"])
    recorded = {"bare": {"count": 0, "sites": []},
                "sys-path": {"count": 0, "sites": []},
                "syntax": {"count": 0, "sites": []}}
    for key, value in counts(root).items():
        recorded[key]["count"] = value
        recorded[key]["sites"] = sites.get(key, [])
    path = root / BASELINE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(recorded, indent=2, sort_keys=True) + "\n")
    return path


def render(items: list[dict]) -> str:
    if not items:
        return "[import-roots] OK: no test file carries its own path entry, and no scripts/ module is imported bare"
    lines = [f"[import-roots] {len(items)} finding(s):"]
    lines += [f"  {it['where']}: {it['detail']}" for it in items]
    return "\n".join(lines)


def render_ratchet(items: list[dict]) -> str:
    """The refusal per NEW site that crossed the recorded baseline (issue #1066/#1101).

    Each goes on its own line naming the exact `file:line`, with the count delta — the author of the new
    root reads their own file here instead of diffing 33 sites. A count-shaped baseline (no site set)
    falls back to naming every site the rule counted, the pre-#1101 output.
    """
    lines: list[str] = []
    for it in items:
        if "over" not in it:                            # a missing baseline: no rule counted anything
            lines.append(f"[import-roots] {it['where']}: {it['detail']}")
            continue
        if it.get("shape") == "set":
            # set-shaped baseline: the NEW site(s) are named precisely, and any removal reported too.
            for site in it.get("new") or []:
                lines.append(f"[import-roots] NEW {it['key']} entry: {site} "
                             f"({it['now']} now, {it['was']} recorded)")
            for site in it.get("removed") or []:
                lines.append(f"[import-roots] removed: {site}  (allowed — the migration may shrink)")
        else:
            # count-shaped baseline (pre-#1101 record): the aggregate cannot name the new site, so
            # every site the rule counts is listed; the author's own diff picks the new one out.
            lines.append(f"[import-roots] {it['detail']}")
            sites = it.get("new") or []
            if sites:
                lines.append(f"[import-roots] {it['key']}: over by {it['over']} — the {len(sites)} "
                             f"site(s) this rule counts, and the new one is among them "
                             f"({BASELINE} records a count, not a set):")
                lines += [f"  {site}" for site in sites]
    return "\n".join(lines)


def render_shrinks(items: list[dict]) -> str:
    """The sanctioned-shrink lines, shown when the gate is green so the migration's smallness is visible."""
    return "\n".join(f"[import-roots] {it['key']}: removed {site}  (allowed)"
                     for it in items for site in it.get("removed", []))


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
        if items:
            print(render_ratchet(items), file=sys.stderr)
            return 1
        refused, shrunk = ratchet_delta(root, tuple(args.allow))
        renders = [render_shrinks(shrunk)] if shrunk else []
        renders.append(f"[import-roots] OK: counts at or below the recorded baseline {counts(root)}")
        print("\n".join(renders))
        return 0
    items = findings(root, tuple(args.allow))
    if args.cmd == "report":
        print(render(items))
        print(f"[import-roots] counts: {counts(root)}")
        return 0
    print(render(items), file=sys.stdout if not items else sys.stderr)
    return 1 if items else 0


if __name__ == "__main__":
    raise SystemExit(main())
