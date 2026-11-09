#!/usr/bin/env python3
"""Confine subprocess.* in PRODUCTION python to the policy seam (issues #797, #2229).

Before #797, ~30 scripts defined subprocess wrappers under five spellings and disagreed on what a
non-zero exit does, while 142 direct `subprocess.run`/`check_output`/`Popen` sites sat un-policied.
This gate implements one rule:

    in production code (scripts/ and agents/**/scripts/), a `subprocess.run` / `subprocess.check_output`
    / `subprocess.Popen` call is allowed ONLY in scripts/proc.py (the seam that defines the policies)
    or on a line carrying a `# proc-allow: <reason>` comment. Anything else is a finding.

The `# proc-allow:` comment is the tracked remainder — the visible shrinking list of direct call sites
that a later change must migrate onto `scripts/proc.py` (the four named policies `run_text`/`run_ok`/
`run_checked`/`run_live`). The census (`report`) lists each allowed site with its reason, so the total is a number
a reviewer can watch fall, not an invisible count.

Issue #2229 broadened the walk that was confined to `scripts/` into three populations:

  * scripts/*.py           — production runners, ENFORCED (a bare site makes `check` exit 1)
  * agents/**/scripts/*.py — production bot-lane runners, ENFORCED (new in #2229)
  * tests/*.py             — the behavior harness, SCANNED/SURFACED but NOT enforced

`tests/` is scanned so the 127-file class the #797 policy protects is never invisible again, but a
bare subprocess in a test is not a gate red: a test's whole job is to spawn subprocess and assert on
its output, and a dropped rc there is a test failure, not a version probe reading `""`. Hard-gating
`tests/` would force a whole-tree `# proc-allow:` carve, which is exactly the widened allow-set #2229
AC3 forbids. The seam and a per-site `# proc-allow: <reason>` remain the ONLY two escapes, in the
enforced populations.

Commands:
    check_proc_gate.py check      exit 1 on any bare subprocess.* site in the ENFORCED populations
                                  (scripts/ + agents/**/scripts/); prints the tests/ census too
    check_proc_gate.py report     the census: every `# proc-allow:` site + the bare-site inventory

Usage:
    python3 scripts/check_proc_gate.py check [--root <repo>]
    python3 scripts/check_proc_gate.py report [--root <repo>]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SEAM = "proc.py"

#: The populations the gate reads. `(base, glob, enforced)`: `enforced=True` means a bare site there
#: refuses `check` (exit 1); `enforced=False` means the population is scanned and surfaced in the
#: census (so the #2229 class is countable) but is not a gate red (the test harness).
POPULATIONS = (
    ("scripts", "*.py", True),
    ("agents", "**/scripts/*.py", True),
    ("tests", "*.py", False),
)

#: The subprocess facets the gate confines (call sites, not the import).
CALL_RE = re.compile(r"\bsubprocess\.(run|check_output|Popen)\s*\(")
#: A trailing `# proc-allow: <reason>` on the same line.
ALLOW_RE = re.compile(r"#\s*proc-allow:\s*\S")

NONCODE = {"__init__.py"}


def _is_seam(path: Path) -> bool:
    return path.name == SEAM


def sites(root: Path) -> list[dict]:
    """Every `subprocess.run/check_output/Popen` site in the three populations, tagged allowed/bare.

    A site is `allowed` when its file is scripts/proc.py or its line carries a `# proc-allow:` reason;
    otherwise it is `bare`. Each finding carries the file, line, the snippet, the reason (when tagged),
    and whether its population is enforced. The gate refuses the `bare` ones in the ENFORCED
    populations only; the census (`report`) shows every population.
    """
    out: list[dict] = []
    for base, glob, enforced in POPULATIONS:
        for path in sorted((root / base).glob(glob if base != "agents" else glob)):
            if path.name in NONCODE:
                continue
            rel = str(path.relative_to(root))
            try:
                text = path.read_text()
            except OSError:
                continue
            for i, line in enumerate(text.splitlines(), 1):
                if not CALL_RE.search(line):
                    continue
                allow = ALLOW_RE.search(line)
                reason = ""
                if allow:
                    reason = re.sub(r"^.*?#\s*proc-allow:\s*", "", line).strip()
                out.append({
                    "where": f"{rel}:{i}",
                    "allowed": _is_seam(path) or bool(allow),
                    "seam": _is_seam(path),
                    "enforced": enforced,
                    "population": base,
                    "reason": reason,
                    "snippet": line.strip(),
                })
    return out


def bare_sites(root: Path = REPO) -> list[dict]:
    """Only the refusals — bare subprocess sites in the ENFORCED populations (no seam/allow)."""
    return [s for s in sites(root) if not s["allowed"] and s["enforced"]]


def allowed_sites(root: Path = REPO) -> list[dict]:
    """The census — every subprocess site the gate allows (in proc.py or `# proc-allow:`-tagged)."""
    return [s for s in sites(root) if s["allowed"]]


def render(items: list[dict], total: int, tests_total: int, tests_bare: int) -> str:
    if not items:
        lines = ["[proc-gate] OK: every subprocess.run/check_output/Popen in scripts/ and "
                 "agents/**/scripts/ is in scripts/proc.py or on a # proc-allow: line"]
    else:
        lines = [f"[proc-gate] {len(items)} bare subprocess call site(s) in scripts/ + "
                 f"agents/**/scripts/ (allowed only in scripts/proc.py or on a line carrying "
                 f"`# proc-allow: <reason>`):"]
        for it in items:
            lines.append(f"  {it['where']}: {it['snippet'][:90]}")
    lines.append(f"[proc-gate] tests/ surfaced: {tests_total} direct subprocess site(s) "
                 f"({tests_bare} bare — the behavior harness, not enforced)")
    return "\n".join(lines)


def render_report(root: Path = REPO) -> str:
    all_sites = sites(root)
    allowed = [s for s in all_sites if s["allowed"]]
    enforced_bare = bare_sites(root)
    tests_bare = [s for s in all_sites if not s["allowed"] and s["population"] == "tests"]
    lines = [
        f"[proc-gate] census — {len(all_sites)} direct subprocess call site(s) across "
        f"scripts/ + agents/**/scripts/ (enforced) + tests/ (surfaced) "
        f"({len(allowed)} allow-listed, {len(enforced_bare)} bare-enforced). The allow-list is the "
        f"tracked remainder; migrate each onto scripts/proc.py to shrink it (issue #797, #2229).",
    ]
    for it in allowed:
        via = "scripts/proc.py" if it["seam"] else "# proc-allow:"
        reason = "" if it["seam"] else (f" ({it['reason']})" if it["reason"] else "")
        pfx = "ENF" if it["enforced"] else "TST"
        lines.append(f"  OK {it['where']}  [{pfx} via {via}{reason}]")
    if enforced_bare:
        lines.append(f"[proc-gate] {len(enforced_bare)} ENFORCED bare site(s) — these must go onto "
                     f"the seam or get a # proc-allow: reason:")
        for it in enforced_bare:
            lines.append(f"  BARE {it['where']}: {it['snippet'][:90]}")
    if tests_bare:
        lines.append(f"[proc-gate] {len(tests_bare)} tests/ bare site(s) — surfaced, not enforced "
                     f"(the behavior harness, #2229):")
        for it in tests_bare:
            lines.append(f"  TST {it['where']}: {it['snippet'][:90]}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="check_proc_gate", description=__doc__)
    p.add_argument("cmd", choices=("check", "report"))
    p.add_argument("--root", default=str(REPO))
    args = p.parse_args(argv)
    root = Path(args.root).resolve()
    if args.cmd == "report":
        print(render_report(root))
        return 0
    all_sites = sites(root)
    items = bare_sites(root)
    tests_all = [s for s in all_sites if s["population"] == "tests"]
    tests_bare = [s for s in tests_all if not s["allowed"]]
    print(render(items, len(all_sites), len(tests_all), len(tests_bare)))
    return 1 if items else 0


if __name__ == "__main__":
    raise SystemExit(main())
