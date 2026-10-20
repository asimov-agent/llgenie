#!/usr/bin/env python3
"""Is every document wired to the Makefile (and to the CI that runs it)? (issue #237)

AGENTS.md: "All verification — locally and in CI — MUST run through the Makefile" and
"A new test file is invisible until a make target names it". Nothing enforced either, so
a `tests/test_*.py` that no target names ran in NO gate while the PR stayed green
(`tests/test_engine_bump_build.py` was exactly that). This is the wiring graph, computed
from the real files:

  check_wiring.py report    print what is wired how, and the host-only exceptions
  check_wiring.py check     exit 1 on an unwired document, a stale exception, a workflow
                            that calls a make target that does not exist, or a target that
                            is not declared `.PHONY`

What "wired" means — one graph, no guessing:

- a **document** is a tracked `tests/test_*.py`, `scripts/*.py`, or a workflow file;
- a **make target** names documents in its recipe (a path like `tests/test_x.py`) and
  calls other targets (`$(MAKE) y` / `make y`);
- a **workflow step** names documents and calls targets the same way;
- a document is **wired** when it is named by a make target or a workflow step, or is
  reachable transitively (a wired script runs it — `scripts/engine_smoke.py` runs
  `tests/test_engine_runs.py`) or is imported by a wired module;
- a document that exists but is named by no target at all is an **ERROR**: it runs in no
  gate, so it reads as coverage while proving nothing;
- a document named only by targets that **CI does not reach** must be recorded in
  `tests/fixtures/host-only-wiring.json` (reason + the target a human runs by hand) —
  a decision, not an accident. A recorded one that CI now reaches is **stale** and must
  be deleted, so the file cannot rot either — and every `make <target>` a workflow calls
  must exist, because a typo in a `run:` block is a silent no-op;
- a **target** whose `##` help line CLAIMS CI coverage ("CI: ...", "CI job x", "Fails CI
  when ...", "(CI pipelines)") must be reached by a CI job, transitively through the
  targets a workflow calls. A help line that promises coverage nothing delivers is the
  same lie as an unwired document, read by a human at `make help` time: correct the line,
  wire the target, or record the decision under `"targets"` in the same file (issue #239);
- an **undeclared `.PHONY` target** is an ERROR (issue #392): `make` runs a recipe when no
  file carries the target's name, so a target that produces no such file MUST be in the
  `.PHONY:` block — otherwise any file named after it (a scratch file, a checkout on a
  case-insensitive filesystem) shadows it and the target reports success having run
  nothing. A target that genuinely produces a file of its own name is recorded under
  `"not_phony"` in the same decisions file instead.

Stdlib only.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MAKEFILES = ("Makefile", "tools/Makefile")
WORKFLOW_DIR = ".github/workflows"
EXCEPTIONS = "tests/fixtures/host-only-wiring.json"
#: The unit-suite aggregator (issue #393): a target that runs it runs the files it selects.
AGGREGATOR = "scripts/unit_tests.py"

#: A `##` help line CLAIMS CI coverage when it says so in one of the ways the tree actually does.
CI_CLAIM_RE = re.compile(r"^\s*CI\b|\bCI job\b|\bCI pipelines\b|\(CI\b|\bFails CI\b")
DOC_PATTERNS = ("tests/test_*.py", "scripts/*.py")
TARGET_RE = re.compile(r"^([a-z0-9][a-z0-9._-]*):", re.M)
DOC_RE = re.compile(r"(tests/[A-Za-z0-9_./-]+\.py|scripts/[A-Za-z0-9_./-]+\.py)")
# `make x`, `$(MAKE) x`, `make -j4 x`, `make -C tools x` — the directory form is followed
# to its target so a `-C tools` call wires the tools/Makefile recipe it runs.
MAKE_RE = re.compile(r"(?:\$\(MAKE\)|make)(?:\s+-(?!C\s)[^\s$]+)*\s+(?:-C\s+\S+\s+)?"
                     r"([a-z0-9][a-z0-9._-]*)(?=\s|$)")


def _recipes(root: Path) -> tuple[dict[str, str], dict[str, set]]:
    """(target -> recipe text, target -> prerequisites). A prerequisite is a real edge:
    `ci-lint: bash-check` means CI running ci-lint runs bash-check."""
    text = "\n\n".join((root / rel).read_text() for rel in MAKEFILES if (root / rel).exists())
    spans = [(m.group(1), m.start()) for m in TARGET_RE.finditer(text)]
    out, prereqs = {}, {}
    for i, (name, start) in enumerate(spans):
        end = spans[i + 1][1] if i + 1 < len(spans) else len(text)
        block = text[start:end]
        out[name] = block
        header = block.splitlines()[0]
        prereqs[name] = set(re.findall(r"[a-z0-9][a-z0-9._-]*", header.split(":", 1)[1]))
        prereqs[name].discard(name)
    return out, prereqs


def _phony_targets(root: Path) -> set[str]:
    """Every name declared `.PHONY` in the Makefiles (issue #392).

    The declaration is one hand-written list with line continuations, so read the raw text:
    a line ending in `\\` continues the same `.PHONY:` block. A name in `.PHONY` that is not
    a target is harmless to make, so only the targets are compared against it.
    """
    out: set[str] = set()
    for rel in MAKEFILES:
        path = root / rel
        if not path.exists():
            continue
        lines = path.read_text().splitlines()
        for i, line in enumerate(lines):
            if not line.startswith(".PHONY:"):
                continue
            chunk = [line.split(":", 1)[1]]
            j = i
            while chunk[-1].rstrip().endswith("\\") and j + 1 < len(lines):
                j += 1
                chunk.append(lines[j])
            out |= set(re.findall(r"[A-Za-z0-9][A-Za-z0-9._-]*",
                                  " ".join(c.rstrip().rstrip("\\") for c in chunk)))
    return out


def _workflow_steps(root: Path) -> dict[str, str]:
    """Every workflow file -> the text of its step bodies (its `run:` blocks + `name:`s)."""
    out = {}
    for wf in (root / WORKFLOW_DIR).glob("*.yml"):
        text = wf.read_text()
        body = "\n".join(line for line in text.splitlines() if not line.strip().startswith("#"))
        out[wf.name] = body
    return out


def _imports(path: Path) -> tuple[set[str], set[str]]:
    """(modules, paths) a python document references.

    A **module** is a real dependency wherever it appears (`import engine_deps`, or a test
    importing `scripts.ci_health`) — whoever imports it exercises it. A **path** is a
    pointer at another document: a subprocess argv, a file the test reads
    (`tests/test_macos_install.py` uses `scripts/loopback_server.py`), a script that runs
    a test (`scripts/engine_smoke.py` runs `tests/test_engine_runs.py`). The one exception
    is a path named only to assert its ABSENCE (`assert "tests/x.py" not in recipe`),
    which wires nothing — that is how a dead file would otherwise look wired."""
    text = path.read_text(errors="ignore")
    lit = {line for line in text.splitlines() if "not in" not in line}
    modules = set()
    paths = {m.rsplit("/", 1)[-1].removesuffix(".py") for line in lit for m in DOC_RE.findall(line)}
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return modules, paths
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules |= {a.name.rsplit(".", 1)[-1] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules |= {node.module.rsplit(".", 1)[-1]}
            modules |= {a.name for a in node.names}
    return modules, paths


def _aggregated(root: Path, recipes: dict[str, str], docs: list[str]) -> tuple[dict[str, set], list[str]]:
    """`{target: the documents it runs through the unit-suite aggregator}` (issue #393), and any
    error reading it.

    `make test-unit` runs `scripts/unit_tests.py`, which computes the hermetic suite from the tree
    (every `tests/test_*.py` minus the dated exclusions in `tests/fixtures/unit-suite.json`). The
    recipe text no longer names those files — that is the whole point — so naming-in-recipe cannot
    be the only evidence a document runs. The aggregator IS the namer: a document in its selection
    is named by every target whose recipe runs it. The selection is read from the script in the
    tree being checked, so there is ONE definition of the suite and no second list to rot."""
    script = root / AGGREGATOR
    if not script.exists():
        return {}, []
    runners = {t for t, r in recipes.items() if AGGREGATOR in r}
    if not runners:
        return {}, []
    try:
        proc = subprocess.run([sys.executable, str(script), "list", "--root", str(root)],
                              capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError) as exc:  # a broken aggregator is a finding
        return {}, [f"{AGGREGATOR} could not list the unit suite ({exc})"]
    if proc.returncode != 0:
        last = proc.stderr.strip().splitlines()[-1] if proc.stderr.strip() else ""
        return {}, [f"{AGGREGATOR} failed to list the unit suite (rc={proc.returncode}): {last}"]
    selection = {d.strip() for d in proc.stdout.splitlines() if d.strip() and d.strip() in set(docs)}
    return {t: selection for t in runners}, []


def documents(root: Path = REPO) -> list[str]:
    """Every tracked document that must be wired, root-relative."""
    return sorted(f"tests/{p.name}" for p in (root / "tests").glob("test_*.py")) + \
        sorted(f"scripts/{p.name}" for p in (root / "scripts").glob("*.py")
               if p.name != "__init__.py")


def _close(root: Path, docs: list[str], recipes: dict[str, str], calls: dict[str, set],
           target_seeds, doc_seeds: set[str] | frozenset[str] = frozenset(),
           extra_named: dict[str, set] | None = None) -> dict[str, set]:
    """Who reaches which document: seed targets (+ workflow-named docs), following target
    calls and prerequisites, then python dependencies (a wired module/file wires it).

    `extra_named` is the discovery seam (issue #393): documents a target runs through the
    unit-suite aggregator without its recipe naming them."""
    reach: dict[str, set] = {d: set() for d in docs}
    stack, seen = list(target_seeds), set()
    while stack:
        t = stack.pop()
        if t in seen or t not in recipes:
            continue
        seen.add(t)
        for d in DOC_RE.findall(recipes[t]):
            if d in reach:
                reach[d].add(f"make {t}")
        for d in (extra_named or {}).get(t, ()):
            if d in reach:
                reach[d].add(f"make {t} (unit-suite discovery)")
        stack += sorted(calls.get(t, ()))
    for d in doc_seeds:
        if d in reach:
            reach[d].add("workflow")
    # Dependencies: a document wires what it imports and what it runs/reads (see _imports).
    changed = True
    while changed:
        changed = False
        for d in docs:
            if not reach[d]:
                continue
            modules, paths = _imports(root / d)
            for name in modules | paths:
                for cand in docs:
                    if cand.endswith(".py") and Path(cand).stem == name and cand != d and not reach[cand]:
                        reach[cand] = {d}
                        changed = True
    return reach


def _help_lines(root: Path = REPO) -> dict[str, str]:
    """Every target's `##` help line — the text a human reads at `make help` time."""
    mk = root / "Makefile"
    if not mk.exists():
        return {}
    out = {}
    for line in mk.read_text().splitlines():
        m = re.match(r"^([A-Za-z0-9_.-]+):[^#]*##\s*(.+)$", line)
        if m:
            out[m.group(1)] = m.group(2).strip()
    return out


def graph(root: Path = REPO) -> dict:
    """The whole wiring graph, computed from the real files: which target/workflow names
    each document, and which of those targets the CI workflows actually call."""
    recipes, prereqs = _recipes(root)
    steps = _workflow_steps(root)
    docs = documents(root)

    named_by_target = {t: set(DOC_RE.findall(r)) & set(docs) for t, r in recipes.items()}
    calls = {t: ({m.group(1) for m in MAKE_RE.finditer(r)} & set(recipes)) | (prereqs.get(t, set()) & set(recipes))
             for t, r in recipes.items()}
    workflow_targets = {w: {m.group(1) for m in MAKE_RE.finditer(t)} for w, t in steps.items()}
    # a workflow `run:` block that names a document directly (make target-less usage)
    workflow_docs = {d for t in steps.values() for d in DOC_RE.findall(t) if d in docs}
    ci_targets = sorted({t for targets in workflow_targets.values() for t in targets if t in recipes})

    # the discovery seam (issue #393): a target that runs the unit-suite aggregator names every
    # document the aggregator selects, though its recipe lists none of them.
    aggregated, agg_errors = _aggregated(root, recipes, docs)
    for t, selection in aggregated.items():
        named_by_target.setdefault(t, set()).update(selection)

    # the target half of the claim (issue #239): what each `##` help line promises, and which
    # targets CI actually reaches — directly, or through the targets a CI target calls.
    claims = {t: h for t, h in _help_lines(root).items() if CI_CLAIM_RE.search(h)}
    seen, frontier = set(ci_targets), set(ci_targets)
    while frontier:
        frontier = {c for t in frontier for c in calls.get(t, set())} - seen
        seen |= frontier
    return {
        "root": str(root), "recipes": recipes, "calls": calls, "docs": docs,
        "claim_targets": claims, "ci_target_closure": sorted(seen),
        "tests": [d for d in docs if d.startswith("tests/")],
        "scripts": [d for d in docs if d.startswith("scripts/")],
        "workflow_targets": workflow_targets, "ci_targets": ci_targets,
        "aggregated": aggregated, "aggregator_errors": agg_errors,
        "phony": sorted(_phony_targets(root)),
        # wired at all (any target, any workflow) vs reached by the CI workflows
        "reachable": _close(root, docs, recipes, calls, recipes.keys(), workflow_docs, extra_named=aggregated),
        "ci_reachable": _close(root, docs, recipes, calls, ci_targets, workflow_docs, extra_named=aggregated),
    }


def load_exceptions(path: Path) -> dict:
    """The dated decisions: host-only documents (`{doc: {reason, target, decided}}`), targets
    whose help line claims CI coverage nothing delivers (`{target: {reason, decided}}`), and
    targets that genuinely produce a file of their own name (`{target: {reason, decided}}`,
    issue #392)."""
    if not path.exists():
        return {"path": str(path), "documents": {}, "targets": {}, "not_phony": {}}
    data = json.loads(path.read_text())
    docs, tgts = data.get("documents"), data.get("targets") or {}
    not_phony = data.get("not_phony") or {}
    if not isinstance(docs, dict):
        raise SystemExit(f"[check-wiring] {path}: 'documents' must be an object")
    for doc, e in docs.items():
        for k in ("reason", "target", "decided"):
            if not e.get(k):
                raise SystemExit(f"[check-wiring] {path}: {doc!r} lacks {k}")
    if not isinstance(tgts, dict):
        raise SystemExit(f"[check-wiring] {path}: 'targets' must be an object")
    if not isinstance(not_phony, dict):
        raise SystemExit(f"[check-wiring] {path}: 'not_phony' must be an object")
    for tgt, e in not_phony.items():
        for k in ("reason", "decided"):
            if not e.get(k):
                raise SystemExit(f"[check-wiring] {path}: not_phony {tgt!r} lacks {k}")
    for tgt, e in tgts.items():
        for k in ("reason", "decided"):
            if not e.get(k):
                raise SystemExit(f"[check-wiring] {path}: target {tgt!r} lacks {k}")
    return {"path": str(path), "documents": docs, "targets": tgts, "not_phony": not_phony}


def check(g: dict, exceptions: dict) -> list[str]:
    """Errors: a document wired to nothing, a document only a non-CI target reaches and no
    dated exception records, a stale exception, a workflow that calls a make target which
    does not exist (a typo in a `run:` block is a silent no-op), and a target that is not
    declared `.PHONY` (a file with that name makes the target a green no-op, issue #392)."""
    recorded = exceptions.get("documents") or {}
    errors = list(g.get("aggregator_errors") or [])
    for w, targets in g["workflow_targets"].items():
        for t in sorted(targets):
            if t not in g["recipes"]:
                errors.append(f"{w} calls `make {t}`, which is not a target in the Makefile")
    for doc in g["docs"]:
        wired, ci = g["reachable"][doc], g["ci_reachable"][doc]
        if not wired:
            errors.append(f"{doc} is wired to nothing: no make target and no workflow names it, and nothing that "
                          f"runs imports it. Name it in a make target (then it runs), or delete it")
        elif not ci and doc not in recorded:
            errors.append(f"{doc} is reachable only by a target CI never runs "
                          f"({', '.join(sorted(wired))}): record it in {exceptions['path']} with the reason and "
                          f"the target a human runs, or wire it to a target a CI job reaches")
        elif ci and doc in recorded:
            errors.append(f"{exceptions['path']}: {doc!r} runs in CI now ({', '.join(sorted(ci))}) — "
                          f"delete the host-only entry")
    for doc in sorted(recorded):
        if doc not in g["docs"]:
            errors.append(f"{exceptions['path']}: {doc!r} does not exist — delete the entry")

    # The target half: a help line that claims CI coverage nothing delivers (issue #239).
    recorded_t = exceptions.get("targets") or {}
    ci_reaches = set(g.get("ci_target_closure") or ())
    for tgt, help_text in sorted((g.get("claim_targets") or {}).items()):
        if tgt in ci_reaches or tgt in recorded_t:
            continue
        errors.append(f"`make {tgt}` claims CI coverage in its help line ({help_text[:70]!r}) but no CI job "
                      f"reaches it: correct the `##` line, wire it to a target a CI job calls, or record the "
                      f"decision under \"targets\" in {exceptions['path']}")
    for tgt in sorted(recorded_t):
        if tgt not in g["recipes"]:
            errors.append(f"{exceptions['path']}: target {tgt!r} is not a make target — delete the entry")
        elif tgt in ci_reaches:
            errors.append(f"{exceptions['path']}: `make {tgt}` is reached by CI now — delete the entry")

    # The .PHONY half (issue #392): make decides to run a recipe by looking for a FILE with the
    # target's name, so a target that produces no such file must be declared `.PHONY` or any file
    # carrying that name (a scratch file, a checkout on a case-insensitive filesystem) shadows it —
    # `make: 'test-env' is up to date.` and no recipe runs. Green, and nothing ran.
    phony = set(g.get("phony") or ())
    recorded_p = exceptions.get("not_phony") or {}
    for target in sorted(g["recipes"]):
        if target in phony or target in recorded_p:
            continue
        errors.append(f"`make {target}` is not declared .PHONY: a file named {target!r} in the "
                      f"checkout shadows it and the target runs NOTHING while reporting success "
                      f"(add it to the `.PHONY:` block, or record a target that produces a file of "
                      f"its own name under \"not_phony\" in {exceptions['path']})")
    for target in sorted(recorded_p):
        if target not in g["recipes"]:
            errors.append(f"{exceptions['path']}: not_phony {target!r} is not a make target — "
                          f"delete the entry")
        elif target in phony:
            errors.append(f"{exceptions['path']}: `make {target}` is declared .PHONY now — "
                          f"delete the not_phony entry")
    return errors


def report(g: dict, exceptions: dict) -> str:
    docs = g["docs"]
    ci = [d for d in docs if g["ci_reachable"][d]]
    recorded = exceptions.get("documents") or {}
    lines = [f"[check-wiring] {len(docs)} documents ({len(g['tests'])} tests, {len(g['scripts'])} scripts): "
             f"{len(ci)} run in CI, {len(recorded)} host-only, {len(g['recipes'])} make targets, "
             f"CI calls {len(g['ci_targets'])} of them"]
    for doc in sorted(recorded):
        e = recorded[doc]
        lines.append(f"  host-only: {doc} — {e['reason']} (run: make {e['target']})")
    aggregated = g.get("aggregated") or {}
    if aggregated:
        for tgt in sorted(aggregated):
            lines.append(f"  discovery: `make {tgt}` runs {len(aggregated[tgt])} file(s) through "
                         f"{AGGREGATOR} without naming them in its recipe")
    claims = g.get("claim_targets") or {}
    reached = set(g.get("ci_target_closure") or ())
    lines.append(f"  {len(claims)} target(s) claim CI coverage in their help line, "
                 f"{len([t for t in claims if t in reached])} are reached by CI")
    phony = set(g.get("phony") or ())
    not_phony = exceptions.get("not_phony") or {}
    unphony = sorted(set(g["recipes"]) - phony - set(not_phony))
    lines.append(f"  {len(phony)} target(s) declared .PHONY, {len(not_phony)} recorded as producing a "
                 f"file of their own name, {len(unphony)} undeclared")
    for tgt in unphony:
        lines.append(f"  NOT .PHONY: make {tgt}")
    for tgt in sorted(set(claims) - reached):
        lines.append(f"  CLAIMS CI, NOT REACHED: make {tgt}")
    for doc in docs:
        if not g["reachable"][doc]:
            lines.append(f"  UNWIRED: {doc}")
        elif not g["ci_reachable"][doc] and doc not in recorded:
            lines.append(f"  NOT IN CI: {doc} (only {', '.join(sorted(g['reachable'][doc]))})")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Is every document wired to the Makefile? (issue #237)")
    ap.add_argument("cmd", choices=("report", "check", "json"))
    ap.add_argument("--root", default=str(REPO), help="the checkout to read (default: this repo)")
    ap.add_argument("--exceptions", default=None,
                    help=f"the host-only decisions (default: <root>/{EXCEPTIONS})")
    a = ap.parse_args(argv)
    root = Path(a.root)
    g = graph(root)
    exceptions = load_exceptions(Path(a.exceptions) if a.exceptions else root / EXCEPTIONS)
    if a.cmd == "json":
        print(json.dumps({"reachable": {k: sorted(v) for k, v in g["reachable"].items()},
                          "named_by_target": {k: sorted(v) for k, v in g["named_by_target"].items()},
                          "workflow_targets": g["workflow_targets"]}, indent=2))
        return 0
    if a.cmd == "report":
        print(report(g, exceptions))
        return 0
    errors = check(g, exceptions)
    for e in errors:
        print(f"[check-wiring] {e}", file=sys.stderr)
    if errors:
        return 1
    print(f"[check-wiring] OK {report(g, exceptions).splitlines()[0][len('[check-wiring] '):]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
