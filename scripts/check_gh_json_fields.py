#!/usr/bin/env python3
"""The gh `--json` field-name guard (issue #515).

`#513` reached `main` because `gh pr view --json …authorAssociation…` is not a
field `gh` has: `gh` refuses the WHOLE call with `Unknown JSON field: "<name>"`
(exit 1), the bot crashes before doing any work, and `make test-unit` never sees
the name because the fake `gh` never looked at it. `#514` fixed that ONE call
site by comparing `auto_merge.PR_VIEW_FIELDS` against a captured allowlist.

This is that seam generalised: one checker that finds every `--json` argument in
`scripts/*.py` and in the workflow shell lanes for the `gh pr|issue|run`
subcommands, resolves the field list statically, and validates every name
against the per-subcommand allowlist the gh CLI itself prints on
`gh <cmd> --json __probe__` (recorded in
`tests/fixtures/gh-json-fields.json`).

It fails CLOSED: a `--json` it cannot attribute to a known subcommand, or whose
field list it cannot resolve statically, is a FINDING, not a skip.

Usage:
  check-gh-json-fields [--root REPO] [--json]
Exit 0 when clean, 1 with one line per finding.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "gh-json-fields.json"

#: first-level gh subcommands whose `--json` has a documented field list.
GH_SUBCOMMANDS = ("pr", "issue", "run")

#: `--json` occurrences that are the SCRIPT's own CLI flag, not a gh argument.
OWN_CLI_RE = re.compile(r'add_argument\(\s*"--json"')
#: a shell `gh <sub1> <sub2> … --json <fields?>` (workflow lanes).
SHELL_CALL_RE = re.compile(r"\bgh\s+([a-z][a-z-]*)\s+([a-z][a-z-]*)([^\n]*)")
SHELL_JSON_TOKEN_RE = re.compile(r"--json[\s\"']+([^\s\"']*)")


def load_allowlists(fixture: Path) -> dict[str, list[str]]:
    data = json.loads(fixture.read_text())
    return {cmd: sorted(fields) for cmd, fields in data["commands"].items()}


def _const_fields(node: ast.AST, consts: dict[str, list[str]]):
    """Resolve a node to a list of field names, or None when unresolvable."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [f for f in node.value.split(",") if f]
    if isinstance(node, ast.Name):
        return consts.get(node.id)
    if isinstance(node, ast.Attribute):
        return consts.get(node.attr)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _const_fields(node.left, consts)
        right = _const_fields(node.right, consts)
        if left is not None and right is not None:
            return left + right
        return None
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        if node.func.attr == "join" and node.args:
            return _const_fields(node.args[0], consts)
    if isinstance(node, (ast.List, ast.Tuple)) and all(
        isinstance(e, ast.Constant) and isinstance(e.value, str) for e in node.elts
    ):
        return [e.value for e in node.elts]
    return None


def collect_consts(tree: ast.AST) -> dict[str, list[str]]:
    """File-local name -> field-list constants (str constants split on commas)."""
    consts: dict[str, list[str]] = {}
    for node in ast.walk(tree):
        target = None
        value = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            target, value = node.targets[0].id, node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            target, value = node.target.id, node.value
        if target is None:
            continue
        fields = _const_fields(value, consts)
        if fields is not None:
            consts[target] = fields
    return consts


def _attr_subpair(els: list[ast.expr]) -> tuple[str, str] | None:
    """From an argv-style list, attribute the gh subcommand pair."""
    strings = [e.value for e in els if isinstance(e, ast.Constant) and isinstance(e.value, str)]
    start = 0
    if "gh" in strings:
        start = strings.index("gh") + 1
    for i in range(start, min(start + 4, len(strings))):
        if strings[i] in GH_SUBCOMMANDS:
            sub1 = strings[i]
            for j in range(i + 1, min(i + 3, len(strings))):
                tok = strings[j]
                if tok.startswith("--"):
                    continue
                return (sub1, tok)
            return (sub1, "")
    return None


def _rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def scan_py_file(path: Path, allow: dict[str, list[str]], root: Path) -> list[dict]:
    findings: list[dict] = []
    src = path.read_text()
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return findings
    consts = collect_consts(tree)

    def finding(node: ast.AST, kind: str, detail: str, sub: str = "") -> None:
        findings.append(
            {"file": _rel(path, root), "line": node.lineno,
             "kind": kind, "sub": sub, "detail": detail}
        )

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == "add_argument" and node.args \
                and isinstance(node.args[0], ast.Constant) and node.args[0].value == "--json":
            continue  # the script's own --json CLI flag, not a gh call
        if not isinstance(node, ast.List):
            continue
        strs = [e.value for e in node.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)]
        if "--json" not in strs:
            continue
        pos = next(i for i, e in enumerate(node.elts)
                   if isinstance(e, ast.Constant) and e.value == "--json")
        subpair = _attr_subpair(node.elts)
        if subpair is None:
            if "gh" in strs:
                finding(node, "unattributable-subcommand",
                        "--json in a gh argv list with no known subcommand")
            continue  # not a gh-attributed list at all (own CLI defaults etc.)
        sub = " ".join(part for part in subpair if part)
        if sub not in allow:
            finding(node, "unattributable-subcommand", f"--json under 'gh {sub}'", sub)
            continue
        if pos + 1 >= len(node.elts):
            finding(node, "unresolvable-fields", "--json with no field argument", sub)
            continue
        fields = _const_fields(node.elts[pos + 1], consts)
        if fields is None:
            finding(node, "unresolvable-fields",
                    f"fields for 'gh {sub}' not statically resolvable", sub)
            continue
        for name in fields:
            if name not in allow[sub]:
                finding(node, "unknown-field",
                        f"'{name}' is not a gh {sub} field", sub)
    return findings


def scan_shell_file(path: Path, allow: dict[str, list[str]], root: Path) -> tuple[list[dict], int]:
    findings: list[dict] = []
    shell_sites = 0
    for lineno, line in enumerate(path.read_text().splitlines(), 1):
        for m in SHELL_CALL_RE.finditer(line):
            head = m.group(3)
            jm = SHELL_JSON_TOKEN_RE.search(head)
            if jm is None:
                continue
            shell_sites += 1
            sub = f"{m.group(1)} {m.group(2)}"
            token = jm.group(1)
            if m.group(1) not in GH_SUBCOMMANDS or sub not in allow:
                findings.append({"file": _rel(path, root), "line": lineno,
                                 "kind": "unattributable-subcommand", "sub": sub,
                                 "detail": "shell-lane gh call"})
                continue
            if not token or "$" in token or "{" in token:
                findings.append({"file": _rel(path, root), "line": lineno,
                                 "kind": "unresolvable-fields", "sub": sub,
                                 "detail": "shell-lane --json fields not a literal list"})
                continue
            for name in token.split(","):
                if name and name not in allow[sub]:
                    findings.append({"file": _rel(path, root), "line": lineno,
                                     "kind": "unknown-field", "sub": sub,
                                     "detail": f"'{name}' is not a gh {sub} field"})
    return findings, shell_sites


def run(root: Path, fixture: Path) -> tuple[list[dict], dict]:
    allow = load_allowlists(fixture)
    findings: list[dict] = []
    sites = 0
    scripts = set()
    for path in sorted(root.glob("scripts/*.py")):
        found = scan_py_file(path, allow, root)
        findings.extend(found)
        src = path.read_text()
        if '"--json"' in src or "--json " in src:
            # count gh-attributed sites the same way the scan saw them
            try:
                tree = ast.parse(src)
                for node in ast.walk(tree):
                    if isinstance(node, ast.List):
                        strs = [e.value for e in node.elts
                                if isinstance(e, ast.Constant) and isinstance(e.value, str)]
                        if "--json" in strs and (
                                _attr_subpair(node.elts) is not None or "gh" in strs):
                            sites += 1
                            scripts.add(str(path.relative_to(root)))
            except SyntaxError:
                pass
    shell_sites = 0
    for path in sorted((root / ".github" / "workflows").glob("*.yml")):
        shell_findings, count = scan_shell_file(path, allow, root)
        findings.extend(shell_findings)
        if count:
            shell_sites += count
            scripts.add(_rel(path, root))
    sites += shell_sites
    coverage = {"sites": sites, "scripts": len(scripts), "findings": len(findings)}
    return findings, coverage


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="check_gh_json_fields")
    ap.add_argument("cmd", nargs="?", default="check", choices=("check",))
    ap.add_argument("--root", default=str(REPO_ROOT))
    ap.add_argument("--fixture", default=str(FIXTURE))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    root = Path(args.root)
    findings, coverage = run(root, Path(args.fixture))
    if args.json:
        print(json.dumps({"coverage": coverage, "findings": findings}))
    else:
        for f in findings:
            print(f"gh-json-fields FAIL {f['file']}:{f['line']} [{f['kind']}] {f['detail']}")
        print(f"gh-json-fields: {coverage['scripts']} scripts, {coverage['sites']} gh --json "
              f"call sites, {len(findings)} finding(s)")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
