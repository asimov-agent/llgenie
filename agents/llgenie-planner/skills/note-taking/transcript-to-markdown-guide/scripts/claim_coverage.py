#!/usr/bin/env python3
"""Does the guide actually carry every load-bearing claim in the transcript?

    python3 scripts/claim_coverage.py <guide.md> <claims.txt|claims.json>

structural and syntax checks pass on a guide that quietly dropped half the
lecture; this is the cheap check for that. Build the claims file by walking the
transcript and writing one distinctive string per fact that must survive into
the guide — a port, an object name, a command, a phrase the section hinges on.

claims file formats
    claims.txt    one needle per line; blank lines and `#` comments ignored
    claims.json   {"label": "needle", ...} for a readable report

Matching is case-insensitive on purpose: a probe written as `vCPU per node`
misses a table header in a different case and reports a false gap. Use the
shortest string that can only come from that fact.

Exit 1 when anything is missing, so it can gate a batch run.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def load_claims(path: Path) -> list[tuple[str, str]]:
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise SystemExit("claims.json must be an object of {label: needle}")
        return [(str(k), str(v)) for k, v in data.items()]
    claims: list[tuple[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        needle = line.strip()
        if not needle or needle.startswith("#"):
            continue
        claims.append((needle, needle))
    return claims


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: claim_coverage.py <guide.md> <claims.txt|claims.json>", file=sys.stderr)
        return 2
    guide_path, claims_path = Path(argv[1]).expanduser(), Path(argv[2]).expanduser()
    if not guide_path.is_file():
        print(f"missing guide: {guide_path}", file=sys.stderr)
        return 2
    if not claims_path.is_file():
        print(f"missing claims file: {claims_path}", file=sys.stderr)
        return 2

    haystack = guide_path.read_text(encoding="utf-8").lower()
    claims = load_claims(claims_path)
    if not claims:
        print("no claims to check", file=sys.stderr)
        return 2

    missing = [(label, needle) for label, needle in claims if needle.lower() not in haystack]
    for label, needle in missing:
        print(f"MISSING  {label}  ->  {needle!r}")
    print(f"{len(claims) - len(missing)}/{len(claims)} claims present in {guide_path.name}")
    if missing:
        print("add the missing facts to the guide, or fix the probe if the fact is there in other words")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
