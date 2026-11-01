#!/usr/bin/env python3
"""Confine `subprocess.*` in scripts/ to the policy seam (issue #797).

Before #797, ~30 scripts defined subprocess wrappers under five spellings and disagreed on what a
non-zero exit does, while 142 direct `subprocess.run`/`check_output`/`Popen` sites sat un-policied.
This gate implements one rule:

    inside scripts/, a `subprocess.run` / `subprocess.check_output` / `subprocess.Popen` call is
    allowed ONLY in scripts/proc.py (the seam that defines the policies) or on a line carrying a
    `# proc-allow: <reason>` comment. Anything else is a finding.

The `# proc-allow:` comment is the tracked remainder — the visible shrinking list of direct call sites
that a later change must migrate onto `scripts/proc.py` (the three named policies `run_text`/`run_ok`/
`run_checked`). The census (`report`) lists each allowed site with its reason, so the total is a number
a reviewer can watch fall, not an invisible count.

Commands:
    check_proc_gate.py check      exit 1 on any bare subprocess.* site in scripts/ (lists file:line)
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
SCRIPTS = "scripts"
SEAM = "proc.py"

#: The subprocess facets the gate confines (call sites, not the import).
CALL_RE = re.compile(r"\bsubprocess\.(run|check_output|Popen)\s*\(")
#: A trailing `# proc-allow: <reason>` on the same line.
ALLOW_RE = re.compile(r"#\s*proc-allow:\s*\S")

NONCODE = {"__init__.py"}


def _is_seam(path: Path) -> bool:
    return path.name == SEAM


def sites(root: Path) -> list[dict]:
    """Every `subprocess.run/check_output/Popen` site in scripts/*.py, tagged allowed/bare.

    A site is `allowed` when its file is scripts/proc.py or its line carries a `# proc-allow:` reason;
    otherwise it is `bare`. Each finding carries the file, line, the snippet, and the reason when one
    is tagged. The gate refuses only the `bare` ones; the census (`report`) shows both.
    """
    out: list[dict] = []
    for path in sorted((root / SCRIPTS).glob("*.py")):
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
                "reason": reason,
                "snippet": line.strip(),
            })
    return out


def bare_sites(root: Path = REPO) -> list[dict]:
    """Only the refusals — direct subprocess sites outside the seam and with no `# proc-allow:`."""
    return [s for s in sites(root) if not s["allowed"]]


def allowed_sites(root: Path = REPO) -> list[dict]:
    """The census — every subprocess site the gate allows (in proc.py or `# proc-allow:`-tagged)."""
    return [s for s in sites(root) if s["allowed"]]


def render(items: list[dict]) -> str:
    if not items:
        return ("[proc-gate] OK: every subprocess.run/check_output/Popen in scripts/ is in "
                "scripts/proc.py or on a # proc-allow: line")
    lines = [f"[proc-gate] {len(items)} bare subprocess call site(s) in scripts/ "
             f"(allowed only in scripts/proc.py or on a line carrying `# proc-allow: <reason>`):"]
    for it in items:
        lines.append(f"  {it['where']}: {it['snippet'][:90]}")
    return "\n".join(lines)


def render_report(root: Path = REPO) -> str:
    all_sites = sites(root)
    allowed = [s for s in all_sites if s["allowed"]]
    bare = [s for s in all_sites if not s["allowed"]]
    lines = [
        f"[proc-gate] census — {len(all_sites)} direct subprocess call site(s) in scripts/ "
        f"({len(allowed)} allow-listed, {len(bare)} bare). The allow-list is the tracked remainder; "
        f"migrate each onto scripts/proc.py to shrink it (issue #797).",
    ]
    for it in allowed:
        via = "scripts/proc.py" if it["seam"] else "# proc-allow:"
        reason = "" if it["seam"] else (f" ({it['reason']})" if it["reason"] else "")
        lines.append(f"  OK {it['where']}  [{via}{reason}]")
    if bare:
        lines.append(f"[proc-gate] {len(bare)} bare site(s) — these must go onto the seam or get a "
                     f"# proc-allow: reason:")
        for it in bare:
            lines.append(f"  BARE {it['where']}: {it['snippet'][:90]}")
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
    items = bare_sites(root)
    print(render(items))
    return 1 if items else 0


if __name__ == "__main__":
    raise SystemExit(main())
