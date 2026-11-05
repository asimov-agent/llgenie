"""Per-cell serve-vs-flags decision for the engine-build matrix.

The engine-build workflow verifies every engine x arch cell. The contract (issue
#1717) is: the binary is PROVEN by `-h`/`--version` flags for every cell; the
OpenAI-serving conformance tier is an explicit opt-in.  When an engine declares
that it can serve on the cell's arch, the workflow MAY serve it (`serve-leg`,
`host-verify`) to prove that tier; when it does NOT declare the arch, the cell
must prove only the binary flags and never run a serve assertion (issue #1748,
owner correction 2026-11-05).

The served-arch truth is `data/engine-capabilities.json` `engines.<id>.archs`
(issue #1214) — never a hand-kept list in the workflow or Makefile.

CLI:
    python3 scripts/engine_capability.py serve <engine> <arch>
        exit 0  -> the engine declares `<arch>` in its `archs` (may serve)
        exit 1  -> the arch is not declared (binary-flags-only; never serve)
        exit 2  -> engine unknown (missing capability row -> safest: flags-only)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CAPABILITIES = REPO / "data" / "engine-capabilities.json"


def declared_archs(engine: str) -> set[str]:
    """The `archs` the engine's capability row declares (empty if unknown)."""
    doc = json.loads(CAPABILITIES.read_text())
    eng = (doc.get("engines") or {}).get(engine) or {}
    return set(eng.get("archs") or [])


def can_serve(engine: str, arch: str) -> bool:
    """True iff the engine declares it can serve on `arch`. Unknown engine -> False."""
    return arch in declared_archs(engine)


def _main(argv: list[str]) -> int:
    if len(argv) != 3 or argv[0] != "serve":
        print(f"usage: {Path(__file__).name} serve <engine> <arch>", file=sys.stderr)
        return 2
    engine, arch = argv[1], argv[2]
    if can_serve(engine, arch):
        print(f"{engine} can serve on {arch} (declared in engine-capabilities.json)")
        return 0
    print(f"{engine} does NOT declare {arch}; binary-flags-only", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
