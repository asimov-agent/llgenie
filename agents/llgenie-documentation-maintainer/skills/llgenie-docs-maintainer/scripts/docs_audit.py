#!/usr/bin/env python3
"""Read-only documentation audit for asimov-agent/llgenie.

Run from the root of the checkout/worktree you want to audit:

    python3 <path>/docs_audit.py            # everything
    python3 <path>/docs_audit.py census      # only the census block

Prints measured facts next to what the docs claim. It never writes. Everything is stdlib so it
runs wherever the repo venv is not active; the Makefile parse is textual, which is enough for
`target:` and `target-%:` anchors.
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path.cwd()
DOCS = sorted(pathlib.Path("docs").glob("*.md"))
TOPDOCS = DOCS + [p for p in (pathlib.Path("README.md"), pathlib.Path("AGENTS.md")) if p.exists()]
DIRS = ["data", "skills", "containers", "tests", "scripts", "openspec", "agent-wiki", "docs"]


def ls(*paths: str) -> list[str]:
    cmd = ["git", "ls-tree", "-r", "--name-only", "HEAD"] + (["--"] + list(paths) if paths else [])
    out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    return [line for line in out.splitlines() if line]


def census() -> None:
    """Print the census; the ARCHITECTURE.md prose is a claim about exactly these numbers."""
    total = len(ls())
    per = {d: len(ls(d)) for d in DIRS}
    tests_py = len([f for f in ls("tests") if re.match(r"test_.*\.py$", f.split("/")[-1])])
    changes = len({f.split("/")[2] for f in ls("openspec/changes")})
    print(f"tracked files: {total}")
    print("per dir: " + ", ".join(f"{d}={n}" for d, n in per.items()))
    print(f"tests/test_*.py: {tests_py}   openspec changes: {changes}")

    # Is each number actually present in the architecture doc? Whitespace-tolerant: the doc wraps
    # its prose, so an exact-token search reports a false miss after a harmless re-wrap.
    arch = pathlib.Path("docs/ARCHITECTURE.md")
    if arch.exists():
        text = arch.read_text()
        want = {
            "tracked files": rf"{total}\s+tracked files",
            "tests/": rf"`tests/`\s+{per['tests']}\b",
            "scripts/": rf"`scripts/`\s+{per['scripts']}\b",
            "openspec/": rf"`openspec/`\s+{per['openspec']}\b",
            "agent-wiki/": rf"`agent-wiki/`\s+{per['agent-wiki']}\b",
            "test_*.py row": rf"{tests_py}\s+`tests/test_\*\.py`",
            "test_*.py prose": rf"unit_tests\.py`\s*\({tests_py}",
            "openspec changes": rf"\({changes}\s+changes\)",
            "agent-wiki entries": rf"\({per['agent-wiki']}\s+entries\)",
        }
        for label, pat in want.items():
            print(f"  claim present [{label}]: {bool(re.search(pat, text))}")

    # Engine-skill-gap census is quoted in prose and must equal the committed JSON.
    gap = pathlib.Path("data/engine-skill-gap.json")
    if gap.exists() and arch.exists():
        import json

        d = json.loads(gap.read_text())
        line = (
            f"{d['registry_engines']} engines, {d['skills']} skills: "
            f"{len(d['shipped'])} shipped ({len(d['imageless_skills'])} with no image), "
            f"{len(d['known_unsupported'])} known-unsupported, {len(d['unresolved'])} unresolved"
        )
        print(f"engine-gap census: {line}")
        print(f"  present in architecture doc: {line in arch.read_text()}")


def scripts_named() -> None:
    """Tracked scripts/*.py that no doc names — usually a surface that landed after a refresh."""
    arch = pathlib.Path("docs/ARCHITECTURE.md")
    if not arch.exists():
        return
    text = arch.read_text()
    missing = [p.name for p in sorted(pathlib.Path("scripts").glob("*.py")) if p.name not in text]
    print(f"scripts/*.py not named in ARCHITECTURE.md: {missing or 'none'}")


def make_targets() -> None:
    """`make <token>` in the docs must be a real target or covered by a `target-%:` pattern."""
    mk = pathlib.Path("Makefile").read_text()
    anchors = set(re.findall(r"^([A-Za-z0-9_.%-]+):(?!=)", mk, re.M))
    pats = [a[:-1] for a in anchors if a.endswith("%")]
    plain = {a for a in anchors if "%" not in a}

    def known(t: str) -> bool:
        return t in plain or any(t.startswith(p) for p in pats)

    for doc in TOPDOCS:
        # Hyphenated tokens only: prose such as "make the target" and "make sure" is not a command.
        used = set(re.findall(r"make\s+(?:-s\s+)?([a-z][a-z0-9]+(?:-[a-z0-9.]+)+)", doc.read_text()))
        bad = sorted(t for t in used if not known(t))
        if bad:
            print(f"{doc}: targets named but not in the Makefile: {bad}")


def workflows() -> list[pathlib.Path]:
    return sorted(pathlib.Path(".github/workflows").glob("*.yml"))


def workflow_claims() -> None:
    """BOTS.md must name every workflow, and its slots table must not omit a scheduled bot."""
    bots = pathlib.Path("docs/BOTS.md")
    if not bots.exists():
        return
    text = bots.read_text()
    files = workflows()
    unnamed = [p.stem for p in files if p.stem not in text]
    print(f"workflow files: {len(files)} | never named in BOTS.md: {unnamed or 'none'}")

    table = dict(re.findall(r"^\|\s*`([a-z0-9-]+)`\s*\|\s*`([^`]+)`", text, re.M))
    scheduled: dict[str, list[str]] = {}
    for p in files:
        crons = [c.strip().strip("\"'") for c in re.findall(r"-\s*cron:\s*[\"']?([^\"'\n]+)", p.read_text())]
        if crons:
            scheduled[p.stem] = crons
    print(f"scheduled workflows: {len(scheduled)} | rows in the slots table: {len(table)}")
    for name, crons in scheduled.items():
        if name not in table:
            print(f"  no slots-table row: {name:26s} {crons}")
        elif table[name] not in crons:
            print(f"  cron mismatch: {name:26s} table={table[name]} workflow={crons}")
    # A `.yml` named in BOTS.md that is not in this repo's workflows is often another repo's file
    # (AUTOMATION.md cites the model repo's qa-validate.yml); only flag files this repo once had.
    ghosts = sorted(
        n for n in set(re.findall(r"`([a-z0-9-]+)\.yml`", text))
        if not (pathlib.Path(".github/workflows") / f"{n}.yml").exists()
    )
    print(f"`.yml` names with no local workflow file (check if they belong to another repo): {ghosts or 'none'}")


def main() -> int:
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if which in ("all", "census"):
        print("== census ==")
        census()
    if which in ("all", "scripts"):
        print("== scripts named in the doc ==")
        scripts_named()
    if which in ("all", "targets"):
        print("== make targets named in the docs ==")
        make_targets()
    if which in ("all", "workflows"):
        print("== workflow / schedule claims ==")
        workflow_claims()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
