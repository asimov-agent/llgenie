#!/usr/bin/env python3
"""Check that every host profile in agents/manifest.json has a row in the fleet doc.

Issue #3106: docs/ARCHITECTURE.md's `## Host lane fleet` subsection is the one place
that claims to enumerate the live Hermes profiles. CI has no live profiles (#928), so
this reads the TREE copy only. The check is deliberately a SUBSET: the manifest must be
documented, but a doc that names an extra lane is not a defect — rosters are meant to
grow and an equality check would red on the next legitimate addition.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SECTION = "Host lane fleet"
MANIFEST = ROOT / "agents" / "manifest.json"
DOC = ROOT / "docs" / "ARCHITECTURE.md"


def manifest_profiles(path: Path) -> list[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    names = [str(item["name"]) for item in data.get("profiles", [])]
    if not names:
        raise ValueError(f"{path}: no profiles declared")
    if len(set(names)) != len(names):
        raise ValueError(f"{path}: duplicate profile names")
    return names


def section_text(doc: str, heading: str = SECTION) -> str:
    """Return the body of `## <heading>` up to the next `## ` heading."""
    lines = doc.splitlines()
    wanted = f"## {heading}".strip().lower()
    start = None
    for idx, line in enumerate(lines):
        if line.strip().lower() == wanted:
            start = idx + 1
            break
    if start is None:
        return ""
    out: list[str] = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        out.append(line)
    return "\n".join(out)


def _display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def documented_names(text: str, names: list[str]) -> set[str]:
    found: set[str] = set()
    for name in names:
        # A name counts when it appears as a standalone token (backticked or plain).
        pattern = rf"(?<![A-Za-z0-9_-]){re.escape(name)}(?![A-Za-z0-9_-])"
        if re.search(pattern, text):
            found.add(name)
    return found


def check(manifest: Path, doc: Path) -> int:
    try:
        profiles = manifest_profiles(manifest)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[fleet-roster] FAIL — unreadable manifest: {exc}")
        return 1
    try:
        text = doc.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"[fleet-roster] FAIL — unreadable fleet doc: {exc}")
        return 1
    section = section_text(text)
    if not section.strip():
        print(
            f"[fleet-roster] FAIL — {_display(doc)} has no `## {SECTION}` "
            f"subsection; {len(profiles)} profile(s) are undocumented"
        )
        return 1
    documented = documented_names(section, profiles)
    missing = [name for name in profiles if name not in documented]
    if missing:
        print(
            f"[fleet-roster] FAIL — {len(missing)} manifest profile(s) absent from "
            f"`## {SECTION}` in {_display(doc)}:"
        )
        for name in missing:
            print(f"  - {name}")
        print("Remedy: add one row per profile to the fleet subsection; never weaken this gate.")
        return 1
    extra = sorted(documented - set(profiles))
    print(
        f"[fleet-roster] OK — all {len(profiles)} manifest profile(s) documented "
        f"in `## {SECTION}` (subset check; {len(extra)} extra name(s) allowed)"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    cmd = sub.add_parser("check", help="check manifest <= documented profiles")
    cmd.add_argument("--manifest", type=Path, default=MANIFEST)
    cmd.add_argument("--doc", type=Path, default=DOC)
    args = parser.parse_args(argv)
    return check(args.manifest, args.doc)


if __name__ == "__main__":
    sys.exit(main())
