#!/usr/bin/env python3
"""The hermetic unit suite is AGGREGATED, never enumerated (issue #393).

`make test-unit` used to name its pytest files by hand: 74 of them on ONE recipe line, so two
PRs that added unrelated tests conflicted on the same line and a name lost while resolving that
conflict silently stopped running. Measured on `main` (`f91d82f`): the file list changed in 63
of the last 300 commits.

This is the ONE place the suite is computed:

    python3 scripts/unit_tests.py list       the selection, one path per line
    python3 scripts/unit_tests.py excluded   what is NOT in the suite, and the target that runs it
    python3 scripts/unit_tests.py argv       the exact pytest invocation `run` execs
    python3 scripts/unit_tests.py check      the roster is consistent (exit 1 with each finding)
    python3 scripts/unit_tests.py run        check, then exec pytest

**Discovery, fail-closed.** The selection is every `tests/test_*.py` MINUS the files
`tests/fixtures/unit-suite.json` records as deliberately not hermetic (each with its reason, its
issue, its date and the target that runs it instead). A new test file is therefore in the gate
the moment it exists, with no shared line to edit — and keeping one OUT of the gate is a dated
decision, not an omission.

**Deselection is exact.** The roster's `deselect` entries become `--deselect
file::test` node ids, never a `-k` expression: `-k` matches substrings, so a new test whose name
CONTAINS a deselected test's name would be silently dropped from the gate.

The shape mirrors the sibling repo (trending-local-llms), whose unit entry is one aggregating
call (`python3 -m pytest tests/ -q`) with the checks that need real network or hardware in their
own targets (`validate-fetch`, `search-smoke`, `model-caps`, `hermes-smoke`).

Stdlib only: it runs inside the test image, and `make check-wiring` imports it.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

#: The roster of deliberate exclusions from the hermetic suite (reason + issue + date + target).
ROSTER = "tests/fixtures/unit-suite.json"
#: What discovery covers: every tracked test module, by name, in the tree.
TEST_GLOB = "tests/test_*.py"
#: The file the roster's `target` entries are resolved against (`<target>:` + its recipe).
MAKEFILE = "Makefile"

REQUIRED_FIELDS = ("reason", "issue", "decided", "target")
MIN_REASON = 40


def _root(root: str | Path | None = None) -> Path:
    """The checkout to read — the repo this file lives in unless a root is given (the tests and
    `make check-wiring` pass one, so the product reads a real scratch tree)."""
    return Path(root).resolve() if root else REPO


def load_roster(root: str | Path | None = None) -> dict:
    """The roster: `excluded` (`{file: {reason, issue, decided, target}}`) and `deselect`
    (`{file: {test: why}}`). A missing or malformed file is fatal: the exclusions are decisions,
    and a decision that cannot be read is not one."""
    path = _root(root) / ROSTER
    if not path.exists():
        raise SystemExit(f"[unit-suite] {ROSTER} is missing — an exclusion from the unit suite has "
                         f"to be a dated decision, never an omission")
    data = json.loads(path.read_text())
    for key in ("excluded", "deselect"):
        if not isinstance(data.get(key), dict):
            raise SystemExit(f"[unit-suite] {ROSTER}: {key!r} must be an object")
    return data


def all_tests(root: str | Path | None = None) -> list[str]:
    """Every `tests/test_*.py` in the tree, root-relative and sorted."""
    return sorted(p.relative_to(_root(root)).as_posix() for p in _root(root).glob(TEST_GLOB))


def excluded(root: str | Path | None = None) -> dict:
    """The files the roster keeps OUT of the hermetic suite, with their decisions."""
    return load_roster(root)["excluded"]


def select(root: str | Path | None = None) -> list[str]:
    """The hermetic unit suite: every test module, minus the roster's recorded exclusions."""
    out = set(excluded(root))
    return [t for t in all_tests(root) if t not in out]


def deselected(root: str | Path | None = None) -> list[str]:
    """The exact pytest node ids the suite de-selects (`deselect` in the roster), sorted."""
    roster = load_roster(root)
    return [f"{f}::{name}" for f, tests in sorted(roster["deselect"].items())
            for name in sorted(tests)]


def argv(root: str | Path | None = None, python: str | None = None) -> list[str]:
    """The pytest invocation: the discovered files, then one `--deselect` per recorded node id."""
    args = [python or sys.executable, "-m", "pytest", *select(root), "-p", "no:cacheprovider", "-q"]
    for node in deselected(root):
        args += ["--deselect", node]
    return args


def _make_recipes(root: Path) -> dict[str, str]:
    """`{target: its recipe block}` for the Makefile, so a roster entry's `target` claim is
    checked against the recipe that would actually run the file."""
    path = root / MAKEFILE
    if not path.exists():
        return {}
    text = path.read_text()
    spans = [(m.group(1), m.start()) for m in re.finditer(r"^([a-z0-9][a-z0-9._-]*):", text, re.M)]
    out = {}
    for i, (name, start) in enumerate(spans):
        end = spans[i + 1][1] if i + 1 < len(spans) else len(text)
        out[name] = text[start:end]
    return out


def _runs_it(root: Path, target: str, doc: str, recipes: dict[str, str]) -> bool:
    """Does `make <target>` actually run `doc`? The recipe names the file, OR the recipe runs a
    `scripts/*.py` that names it — `make test-engine` runs `scripts/engine_smoke.py`, which
    pytest-runs `tests/test_engine_runs.py` inside the engine image. Naming the file in the
    recipe is the direct case; the script hop is the same evidence the wiring guard accepts."""
    recipe = recipes.get(target, "")
    if doc in recipe:
        return True
    for script in re.findall(r"scripts/[A-Za-z0-9_./-]+\.py", recipe):
        path = root / script
        if path.exists() and doc in path.read_text():
            return True
    return False


def check(root: str | Path | None = None) -> list[str]:
    """Every finding that makes the roster inconsistent, as `[unit-suite] …` lines:

    - an exclusion whose file is gone (stale), or missing one of `reason`/`issue`/`decided`/`target`;
    - an exclusion naming a target that is not a make target, or whose recipe does not name the
      file (the roster cannot claim a runner that does not run it);
    - a deselection naming a file that is excluded or gone, a test the file does not define, or
      carrying no reason;
    - an empty selection (a suite that runs nothing must never look green).
    """
    root = _root(root)
    roster = load_roster(root)
    tests = set(all_tests(root))
    recipes = _make_recipes(root)
    errors: list[str] = []

    for doc, entry in sorted(roster["excluded"].items()):
        if doc not in tests:
            errors.append(f"{ROSTER}: {doc!r} does not exist — delete the entry")
            continue
        for field in REQUIRED_FIELDS:
            if not entry.get(field):
                errors.append(f"{ROSTER}: {doc!r} lacks {field}")
        if entry.get("reason") and len(entry["reason"]) < MIN_REASON:
            errors.append(f"{ROSTER}: {doc!r} records no real reason ({entry['reason']!r}) — say why "
                          f"this file is not hermetic and which target runs it instead")
        target = entry.get("target")
        if target:
            if target not in recipes:
                errors.append(f"{ROSTER}: {doc!r} names `make {target}`, which is not a make target")
            elif not _runs_it(root, target, doc, recipes):
                errors.append(f"{ROSTER}: {doc!r} claims `make {target}` runs it, but neither that "
                              f"recipe nor a script it runs names the file")

    for doc, entries in sorted(roster["deselect"].items()):
        if doc not in tests:
            errors.append(f"{ROSTER}: deselect {doc!r} does not exist — delete the entry")
            continue
        if doc in roster["excluded"]:
            errors.append(f"{ROSTER}: {doc!r} is both excluded and deselected — an excluded file is "
                          f"not in the suite to deselect from")
            continue
        body = (root / doc).read_text()
        for name, why in sorted(entries.items()):
            if not why or len(why) < MIN_REASON // 2:
                errors.append(f"{ROSTER}: {doc}::{name} carries no reason")
            if not re.search(rf"^def {re.escape(name)}\(", body, re.M):
                errors.append(f"{ROSTER}: {doc}::{name} is deselected but no test of that name exists "
                              f"in the file — delete the entry")

    if not select(root):
        errors.append("the selection is empty — discovery found no hermetic test at all")
    return errors


def _summary(root: str | Path | None = None) -> str:
    return (f"{len(select(root))} of {len(all_tests(root))} {TEST_GLOB} selected by discovery; "
            f"{len(excluded(root))} excluded by {ROSTER}; {len(deselected(root))} node de-selected")


def report(root: str | Path | None = None) -> str:
    """The whole picture: the counts, then every exclusion with the target that runs it instead."""
    lines = [f"[unit-suite] {_summary(root)}"]
    for doc, entry in sorted(excluded(root).items()):
        lines.append(f"  excluded: {doc} — {entry.get('reason', '')[:110]} (run: make {entry.get('target')})")
    for node in deselected(root):
        lines.append(f"  de-selected: {node}")
    return "\n".join(lines)


def run(root: str | Path | None = None, python: str | None = None) -> int:
    """Check the roster, then exec pytest on the discovered suite. A broken roster is exit 2
    BEFORE pytest runs: a gate must not start from an exclusion record nobody can trust."""
    errors = check(root)
    if errors:
        for e in errors:
            print(f"[unit-suite] {e}", file=sys.stderr)
        print(f"[unit-suite] refusing to start pytest: fix {ROSTER} above", file=sys.stderr)
        return 2
    args = argv(root, python)
    print(f"[unit-suite] {_summary(root)}")
    print(f"[unit-suite] {' '.join(args)}", flush=True)
    return subprocess.call(args)


def main(argv_: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="The aggregated hermetic unit suite (issue #393)")
    ap.add_argument("cmd", choices=("list", "excluded", "argv", "check", "report", "run"))
    ap.add_argument("--root", default=None, help="the checkout to read (default: this repo)")
    a = ap.parse_args(argv_)
    if a.cmd == "list":
        for doc in select(a.root):
            print(doc)
        return 0
    if a.cmd == "excluded":
        print(report(a.root))
        return 0
    if a.cmd == "argv":
        print(" ".join(argv(a.root)))
        return 0
    if a.cmd == "check":
        errors = check(a.root)
        for e in errors:
            print(f"[unit-suite] {e}", file=sys.stderr)
        if errors:
            return 1
        print(f"[unit-suite] OK {_summary(a.root)}")
        return 0
    if a.cmd == "report":
        print(report(a.root))
        return 0
    return run(a.root)


if __name__ == "__main__":
    raise SystemExit(main())
