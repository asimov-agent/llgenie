#!/usr/bin/env python3
"""The scripts/ layering as a gate: cycles fatal, unstated cross-group imports refused (issue #795).

`docs/ARCHITECTURE.md` §Scripts has always presented `scripts/` as five groups — Product path,
Security pipeline, Structural gates, CI entrypoints, Bots and automation — but the grouping lived
only in that table, so no import and no gate could answer "is this module allowed to import that
one", and a reviewer of a long change could not tell whether a new edge crossed a border. This gate
makes the table executable. Its data is `scripts/package-layers.json`:

    groups         every module of `scripts/` -> the one group it belongs to
    allowed_edges  the cross-group imports the repository has agreed to, each with its reason

Four rules, all refusals (never warnings):

    cycle        an import cycle is ALWAYS fatal, whether or not it crosses a group border. The
                 cycle this issue was filed for (`engine_bump` <-> `engine_params_derive`) was a
                 function-local import precisely because nothing could see it.
    cross-group   an import that crosses a border and is not in `allowed_edges` is fatal: state the
                 edge and its reason in the file, or move the module.
    stale        an `allowed_edges` entry that the tree no longer contains (or that no longer
                 crosses a border) is fatal, so the file cannot rot into fiction.
    unknown      a `scripts/` module the file does not place, a module the file places that the tree
                 does not contain, a module in two groups, or a group name the doc's table does not
                 state.

A new module therefore arrives with its group, and a new cross-border import arrives with its
reason — which is the whole point: the border set is agreed in a file a reviewer reads, not
rediscovered per change.

Usage:
    python3 scripts/check_package_layers.py check     # exit 0 = OK, 1 = a finding, 2 = unreadable
    python3 scripts/check_package_layers.py report    # print the layering and the edges, exit 0

Stdlib only: `make ci-unit` runs it on a bare host.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA = Path("scripts/package-layers.json")
SCRIPTS = "scripts"
DOC = Path("docs/ARCHITECTURE.md")


class LayersError(Exception):
    """The layering could not be read at all — exit 2, never a silent pass."""


def script_modules(root: Path) -> set[str]:
    """The importable modules `scripts/` provides (the package marker is not a module)."""
    return {p.stem for p in (root / SCRIPTS).glob("*.py") if p.stem != "__init__"}


def _relative_target(node: ast.ImportFrom) -> list[str]:
    """The module names a `from … import …` names, resolving `.` / `..x` / `scripts.x` spellings."""
    out: list[str] = []
    if node.level:                                   # a relative import inside the package
        if node.module:
            out.append(node.module.split(".")[0])
        else:                                        # `from . import a, b`
            out.extend(a.name for a in node.names)
        return out
    if node.module:
        parts = node.module.split(".")
        out.append(parts[1] if parts[0] == SCRIPTS and len(parts) > 1 else parts[0])
    return out


def module_edges(root: Path) -> dict[str, dict[str, list[int]]]:
    """`{module: {imported module: [line, …]}}` for every `scripts/` module, from the AST.

    Both spellings a `scripts/` module uses are read: the package-relative one (`.proc`) and the
    script-mode fallback (`import proc`, inside `try/except ImportError`). The fallback is the same
    dependency and hiding it is what made the original cycle invisible, so it counts.
    """
    modules = script_modules(root)
    edges: dict[str, dict[str, list[int]]] = {}
    for path in sorted((root / SCRIPTS).glob("*.py")):
        source = path.stem
        if source == "__init__":
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            raise LayersError(f"{SCRIPTS}/{path.name} does not parse: {exc.msg}") from None
        for node in ast.walk(tree):
            targets: list[str] = []
            if isinstance(node, ast.ImportFrom):
                targets = _relative_target(node)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    parts = alias.name.split(".")
                    if parts[0] == SCRIPTS and len(parts) > 1:
                        targets.append(parts[1])
                    else:
                        targets.append(parts[0])
            for target in targets:
                if target in modules and target != "__init__":
                    edges.setdefault(source, {}).setdefault(target, []).append(node.lineno)
    return edges


def strongly_connected(nodes: set[str], edges: dict[str, dict[str, list[int]]]) -> list[list[str]]:
    """Every import cycle (an SCC of more than one module) — a cycle is always fatal."""
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    found: list[list[str]] = []
    counter = 0

    def visit(start: str) -> None:
        nonlocal counter
        work = [(start, iter(sorted(edges.get(start, {}))))]
        index[start] = low[start] = counter
        counter += 1
        stack.append(start)
        on_stack.add(start)
        while work:
            node, children = work[-1]
            advanced = False
            for child in children:
                if child not in index:
                    index[child] = low[child] = counter
                    counter += 1
                    stack.append(child)
                    on_stack.add(child)
                    work.append((child, iter(sorted(edges.get(child, {})))))
                    advanced = True
                    break
                if child in on_stack:
                    low[node] = min(low[node], index[child])
            if advanced:
                continue
            work.pop()
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[node])
            if low[node] == index[node]:
                component: list[str] = []
                while True:
                    member = stack.pop()
                    on_stack.discard(member)
                    component.append(member)
                    if member == node:
                        break
                if len(component) > 1:
                    found.append(sorted(component))

    for node in sorted(nodes):
        if node not in index:
            visit(node)
    return sorted(found)


def doc_groups(root: Path) -> list[str]:
    """The group names the §Scripts table of `docs/ARCHITECTURE.md` states, in order."""
    doc = (root / DOC)
    if not doc.exists():
        return []
    text = doc.read_text(encoding="utf-8")
    start = text.find("## Scripts")
    if start == -1:
        return []
    rest = text[start + len("## Scripts"):]
    end = rest.find("\n## ")
    section = rest if end == -1 else rest[:end]
    names: list[str] = []
    for line in section.splitlines():
        if not line.startswith("|"):
            continue
        label = line.strip().strip("|").split("|")[0].strip()
        if not label or label == "Group" or set(label) <= set("-: "):
            continue
        names.append(label)
    return names


def load(root: Path = REPO_ROOT) -> dict:
    path = root / DATA
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise LayersError(f"{DATA} is missing: the layering is undeclared") from None
    except json.JSONDecodeError as exc:
        raise LayersError(f"{DATA} is not valid JSON: {exc}") from None
    if not isinstance(data, dict) or not isinstance(data.get("groups"), dict):
        raise LayersError(f"{DATA} has no `groups` object")
    return data


def placement(data: dict) -> tuple[dict[str, str], list[str]]:
    """`module -> group`, plus the module names the file places in more than one group."""
    placed: dict[str, str] = {}
    duplicated: list[str] = []
    for group, modules in data["groups"].items():
        if not isinstance(modules, list):
            raise LayersError(f"{DATA}: group {group!r} is not a list of modules")
        for name in modules:
            if name in placed:
                duplicated.append(name)
            placed[name] = group
    return placed, sorted(set(duplicated))


def findings(root: Path = REPO_ROOT) -> list[dict]:
    """Every way the layering and the tree disagree, as one list of findings."""
    data = load(root)
    placed, duplicated = placement(data)
    modules = script_modules(root)
    edges = module_edges(root)
    items: list[dict] = []

    for name in sorted(modules - set(placed)):
        items.append({"key": "unknown-module", "where": f"{SCRIPTS}/{name}.py",
                      "detail": "this module is in no group of the layering: add it to a group in "
                                f"{DATA}, because a module no group holds has no border to respect"})
    for name in sorted(set(placed) - modules):
        items.append({"key": "missing-module", "where": f"{DATA}:{name}",
                      "detail": "the layering places a module the tree no longer has: delete the "
                                "entry, so the file describes the tree rather than its history"})
    for name in duplicated:
        items.append({"key": "duplicate-module", "where": f"{DATA}:{name}",
                      "detail": f"placed in more than one group (last one wins today): a module "
                                "belongs to exactly one group"})

    declared_groups = [g for g in data["groups"]]
    row_labels = doc_groups(root)
    for group in declared_groups:
        if row_labels and group not in row_labels:
            items.append({"key": "unknown-group", "where": f"{DATA}:{group}",
                          "detail": "the doc's §Scripts table states no such group: the data and "
                                    "the map must be read as one thing"})

    for component in strongly_connected(modules, edges):
        items.append({"key": "cycle", "where": " -> ".join(component),
                      "detail": "import cycle: " + ", ".join(
                          f"{a} -> {b}" for a in component for b in sorted(edges.get(a, {}))
                          if b in component)})

    listed = {}
    for edge in data.get("allowed_edges") or []:
        if not isinstance(edge, dict) or "from" not in edge or "to" not in edge:
            raise LayersError(f"{DATA}: every allowed_edges entry needs `from`, `to` and `reason`")
        if not str(edge.get("reason", "")).strip():
            items.append({"key": "stale-edge", "where": f"{edge['from']} -> {edge['to']}",
                          "detail": "an allowed edge needs a one-line reason: an unstated "
                                    "exception is the review opinion this gate replaces"})
        listed[(edge["from"], edge["to"])] = edge

    for source in sorted(edges):
        for target in sorted(edges[source]):
            if placed.get(source) == placed.get(target):
                continue
            if (source, target) not in listed:
                items.append({
                    "key": "cross-group", "where": f"{SCRIPTS}/{source}.py:{edges[source][target][0]}",
                    "detail": f"{placed.get(source)!r} -> {placed.get(target)!r} "
                              f"({source} -> {target}) crosses a border and is not stated in "
                              f"{DATA}: move the module into the group it belongs to, or list the "
                              "edge with its reason",
                })

    for (source, target), edge in sorted(listed.items()):
        if target not in edges.get(source, {}):
            items.append({"key": "stale-edge", "where": f"{edge['from']} -> {edge['to']}",
                          "detail": f"{DATA} allows an edge the tree no longer has: delete the "
                                    "entry, so an exception cannot outlive the import it excused"})
        elif placed.get(source) == placed.get(target):
            items.append({"key": "stale-edge", "where": f"{edge['from']} -> {edge['to']}",
                          "detail": f"{DATA} allows a cross-group edge, but both modules are in "
                                    f"{placed.get(source)!r} now: delete the entry"})
    return items


def measure(root: Path = REPO_ROOT) -> dict:
    """The census a reader can reproduce: groups, modules, edges, intra/cross and cycles."""
    data = load(root)
    placed, _ = placement(data)
    modules = script_modules(root)
    edges = module_edges(root)
    total = sum(len(v) for v in edges.values())
    intra = sum(1 for a, targets in edges.items() for b in targets if placed.get(a) == placed.get(b))
    return {
        "groups": len(data["groups"]),
        "modules": len(modules),
        "placed": len(placed),
        "allowed_edges": len(data.get("allowed_edges") or []),
        "imports": total,
        "intra": intra,
        "cross": total - intra,
        "cycles": len(strongly_connected(modules, edges)),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="the scripts/ layering gate (issue #795)")
    ap.add_argument("command", nargs="?", default="check", choices=("check", "report"))
    ap.add_argument("--root", default=str(REPO_ROOT),
                    help="a tree to read instead of the repo root (a fixture, or an exported copy)")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    try:
        if args.command == "report":
            stats = measure(root)
            data = load(root)
            print(f"{DATA}: {stats['groups']} groups, {stats['modules']} modules "
                  f"({stats['placed']} placed), {stats['allowed_edges']} allowed edges")
            for group, modules in data["groups"].items():
                print(f"  {group}: {len(modules)}")
            print(f"imports: {stats['imports']} ({stats['intra']} intra-group, "
                  f"{stats['cross']} cross-group), cycles: {stats['cycles']}")
            for edge in data.get("allowed_edges") or []:
                print(f"  allowed {edge['from']} -> {edge['to']}: {edge.get('reason', '')}")
            return 0
        items = findings(root)
    except LayersError as exc:
        print(f"check-package-layers: {exc}", file=sys.stderr)
        return 2
    if items:
        for item in items:
            print(f"[{item['key']}] {item['where']}: {item['detail']}")
        print(f"check-package-layers: {len(items)} finding(s)", file=sys.stderr)
        return 1
    stats = measure(root)
    print(f"check-package-layers: OK — {stats['modules']} modules in {stats['groups']} groups, "
          f"{stats['cross']} cross-group edges all stated, {stats['cycles']} cycles")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
