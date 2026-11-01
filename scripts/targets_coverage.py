#!/usr/bin/env python3
"""targets-coverage — every Makefile target and the callers that reach it (issue #1102).

`make -qp` gives 304 targets (13 `_`-prefixed internal) at this tree, but nobody knows which targets no
workflow step or script runs. This module makes that a measurement, not a guess:

- enumerate every target the Makefile defines (projected from `make -qp`, the same method the issue's
  Technical cites — not a fragile line-regex over recipe text alone);
- for each target, find the callers that reach it across the tree: a `make <target>` / `$(MAKE) <target>`
  call in a workflow step (`run:` block), in a script, or in another target's recipe;
- mark `_`-prefixed targets as **internal** so a reader can tell which USER-FACING targets nothing runs;
- emit `target | internal? | callers-found | callers-detail`, then totals: total, internal, user-facing, and
  user-facing with no caller (the actionable set).

Commands:
    targets_coverage.py report          print the coverage table + totals to stdout (default)
    targets_coverage.py --json          same, machine-readable
    targets_coverage.py --root DIR      run against DIR instead of the repo root
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS_DIR = ".github/workflows"
SCRIPTS_DIR = "scripts"
#: `make <target>` or `$(MAKE) <target>` (optionally `make -C <dir> <target>`), in a workflow step body or a
#: script. Anchored: a bare prose mention of the word "make" is not a call.
MAKE_CALL = re.compile(r"(?:make|\$\$\(MAKE\))\s+(?:-C\s+\S+\s+)?([A-Za-z0-9_.-]+)")
#: The target-line shape for the textual fallback (used only when `make -qp` is unavailable). `re.M` is
#: required — without it `^` anchors to the first line only and the projection collapses to one target.
TARGET_LINE = re.compile(r"^([A-Za-z0-9_][A-Za-z0-9_.-]*):", re.M)


def run_make_qp(root: Path) -> str | None:
    """`make -qp` output, or None if make is unavailable / errors so loudly it kills the projection."""
    try:
        r = subprocess.run(["make", "-qp", "-f", "Makefile"], cwd=root,  # proc-allow: direct subprocess call site, tracked remainder for issue #797 (migrate onto scripts/proc.py in a per-module batch)
                           capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            # `make -qp` returns non-zero when a target is "up to date" — that is NOT an error here: the
            # stdout still holds the target database. Only a signal / missing make is a real failure.
            return r.stdout or None
        return r.stdout or None
    except (OSError, subprocess.SubprocessError):
        return None


def targets_from_qp(qp: str) -> set[str]:
    """The Makefile-defined targets in `make -qp` output, excluding make's implicit suffix/pattern rules.

    `_`-prefixed internal targets are real targets, so the leading class accepts `_` — the probe that
    anchored on `[A-Za-z0-9]` silently dropped all 13 internal targets (measured: 291 = 304 − 13).
    """
    out: set[str] = set()
    for line in qp.splitlines():
        m = re.match(r"^([A-Za-z0-9_][A-Za-z0-9_.-]*):", line)
        if not m:
            continue
        out.add(m.group(1))
    return out


def targets_from_makefile_text(text: str) -> set[str]:
    """Fallback target set (regex over Makefile text) when `make -qp` cannot run."""
    return {m.group(1) for m in TARGET_LINE.finditer(text)}


def makefile_targets(root: Path) -> set[str]:
    """The authoritative target set: `make -qp` when possible, else the textual fallback."""
    qp = run_make_qp(root)
    if qp:
        return targets_from_qp(qp)
    mk = root / "Makefile"
    return targets_from_makefile_text(mk.read_text()) if mk.exists() else set()


def callers_for(target: str, root: Path) -> list[tuple[str, str]]:
    """`[(kind, location)]` for every caller of `target`, kind in {workflow, script, target}.

    A caller is a file that contains `make <target>` / `$(MAKE) <target>` in a position that runs it — a
    workflow `run:` block, a script, or another target's recipe. The same target referenced in more than one
    file appears once per (kind, file).
    """
    found: list[tuple[str, str]] = []
    for wf in sorted((root / WORKFLOWS_DIR).glob("*.yml")):
        if MAKE_CALL.search(wf.read_text()):
            if any(MAKE_CALL.search(line) and target in MAKE_CALL.findall(line) for line in wf.read_text().splitlines()):
                found.append(("workflow", wf.name))
    for sp in sorted((root / SCRIPTS_DIR).glob("*.py")):
        body = sp.read_text()
        if target in MAKE_CALL.findall(body):
            found.append(("script", sp.name))
    # other targets' recipes (transitive reach):
    mk = root / "Makefile"
    if mk.exists():
        for line in mk.read_text().splitlines():
            if re.match(r"^[A-Za-z0-9_][A-Za-z0-9_.-]*:", line):
                pass  # a target line itself, not a call
            elif f"make {target}" in line.replace("$(MAKE)", "make"):
                found.append(("target", "Makefile"))
                break
    # de-dupe preserving order
    seen, out = set(), []
    for kind, loc in found:
        key = (kind, loc)
        if key not in seen:
            seen.add(key)
            out.append((kind, loc))
    return out


def coverage_records(targets: set[str], root: Path) -> list[dict]:
    """`[{target, internal, callers: [..]}]` — internal = `_`-prefixed."""
    return [{"target": t, "internal": t.startswith("_"),
             "callers": callers_for(t, root)} for t in sorted(targets)]


def render_report(records: list[dict]) -> tuple[str, int]:
    """The coverage table + totals. Returns (text, exit_code); exit 0 (a report, not a gate)."""
    rows = ["| target | internal | callers |", "|---|---|---|"]
    total_user_facing = 0
    no_caller_user = 0
    for r in records:
        row = (f"| `{r['target']}` | {'internal' if r['internal'] else 'user-facing'} | "
               f"{', '.join(name for _, name in r['callers']) if r['callers'] else 'none'} |")
        rows.append(row)
        if not r["internal"]:
            total_user_facing += 1
            if not r["callers"]:
                no_caller_user += 1
    totals = (f"Totals: {len(records)} targets · "
              f"{sum(1 for r in records if r['internal'])} internal · "
              f"{total_user_facing} user-facing · "
              f"{no_caller_user} user-facing with NO caller (the actionable set)")
    text = "\n".join(rows) + "\n\n" + totals + "\n"
    return text, 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("report", nargs="?", default="report", help="print the coverage table (default)")
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    ap.add_argument("--root", type=Path, default=None, help="repo root (default: this repo)")
    a = ap.parse_args(argv)
    root = (a.root or REPO_ROOT).resolve()
    records = coverage_records(makefile_targets(root), root)
    text, code = render_report(records)
    if a.json:
        print(json.dumps(records, indent=1))
    else:
        print(text)
    return code


if __name__ == "__main__":
    sys.exit(main())
