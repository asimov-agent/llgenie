#!/usr/bin/env python3
"""Report (and sweep) the SUPERSEDED fixed-name buildx registry cache tags (issue #2914).

The buildx registry layer-cache namespaces for helper images and engine bases/cells used to be
FIXED names (`llgenie/<name>:buildcache`, `llgenie/base-<backend>:buildcache`,
`llgenie/<engine>:buildcache-<variant>`) with no link to the content being built. The cache-keying
changes (#2891 / PR #2912, and #2911 / PR #2915) make every build write a CONTENT-HASH-keyed
namespace instead (`<...>-buildcache`). The old fixed tags remain in GHCR as orphaned cache layers.
This tool names them so the sweep is auditable and repeatable, and can delete them once no live
producer writes the fixed name anymore.

Safety is the point: a ref is only an "orphan" when its tag is a fixed cache name AND the repo's
producer seams no longer derive that exact ref. The live producer set is derived from the ONE
sources the build writes with — `scripts/engine_image.py::cache_ref` and `scripts/ci_images.py::
cache_ref` — so:

- while the keying changes are NOT on main, those seams still return the fixed names -> the report
  prints zero orphans (a sweep now would be unsafe; the issue's own gate);
- the moment the keying changes land, the same seams return content-keyed names -> the fixed tags
  they superseded become orphans the report prints and the sweep clears.

Enumeration of what EXISTS in the registry goes through `gh api` on the org's container packages —
the registry seam AGENTS.md's issue describes. Run against the org's packages, and (for the sweep)
only after both keying PRs have landed on main. Hermetically unit-tested with a stubbed `gh`/
producer seam; the live run needs a token that can read (and, to sweep, delete) the org's packages.

Usage (driven by make, never by hand):

    python3 scripts/cache_orphan_report.py report        # print orphan fixed-name cache tags, rc=0
    python3 scripts/cache_orphan_report.py list          # alias for report
    python3 scripts/cache_orphan_report.py sweep         # delete them (gated on no live producer)

LLGENIE_REGISTRY overrides the registry (default ghcr.io/asimov-agent), matching every other seam.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))


def registry() -> str:
    return os.environ.get("LLGENIE_REGISTRY", "ghcr.io/asimov-agent").rstrip("/").lower()


def owner() -> str:
    """The GitHub owner segment of the registry (e.g. `asimov-agent` for ghcr.io/asimov-agent)."""
    reg = registry()
    # scheme, host, owner — reuse ci_images.registry_parts to stay the single owner parse.
    import ci_images
    _, _, own = ci_images.registry_parts()
    return own or reg.split("/")[0]


# ---------------------------------------------------------------------------
# the LIVE producer set — derived ONLY from the seams the build writes with
# ---------------------------------------------------------------------------

def live_cache_refs() -> set[str]:
    """The cache refs the CURRENT repo would still write, from the ONE producer seams.

    Helper refs come from `ci_images.cache_ref`; engine base+cell refs come from
    `engine_image.cache_ref`. Both are the exact seams the builds call, so when the content-hash
    keying lands and edits those seams, this set follows and the superseded fixed tags surface as
    orphans — with no second derivation to keep in sync.
    """
    import ci_images
    import engine_image as ei
    import engine_skills as es

    live: set[str] = set()
    # helpers
    for name in ci_images.IMAGES:
        live.add(ci_images.cache_ref(name))
    # engine cells: one cache ref per committed (engine, variant), the SAME tag formula the build
    # publishes (resolve().tag), so the image NAME matches `make build-engine ENGINE=...` exactly.
    for path in sorted(es.PARAMS_DIR.glob("*.json")):
        params = json.loads(path.read_text())
        for variant, spec in sorted(params["variants"].items()):
            backend = spec.get("backend", "cpu")
            cell = ei.resolve(params["id"], backend, variant)
            image_name = cell["tag"].split(":", 1)[0]
            live.add(ei.cache_ref(image_name, variant))
    # base cache refs: one per committed base Dockerfile backend.
    for dockerfile in sorted(es.BASE_DIR.glob("Dockerfile.*")):
        backend = dockerfile.name.split(".", 1)[1]
        live.add(ei.cache_ref(es.base_image_name(backend)))
    return live


# ---------------------------------------------------------------------------
# what actually exists in the registry (via gh api)
# ---------------------------------------------------------------------------

def _gh_api(args: list[str]) -> list:
    from proc import run_text
    body = run_text(["gh", "api"] + args)
    return json.loads(body)


def _container_packages() -> list[str]:
    """Container package names under the org's `llgenie/` namespace (e.g. llgenie/test)."""
    out = _gh_api(["/orgs/%s/packages" % owner(), "--paginate",
                   "-f", "package_type=container", "-f", "per_page=100"])
    return [p.get("name", "") for p in out
            if p.get("name", "").startswith("llgenie/")]


def _package_versions(package: str) -> list[dict]:
    """Every version of one container package, with its container tags."""
    esc = urllib.parse.quote(package, safe="")
    out = _gh_api(["/orgs/%s/packages/container/%s/versions" % (owner(), esc),
                   "--paginate", "-f", "per_page=100"])
    return out


def _existing_tags() -> dict[str, list[str]]:
    """{package: [tags]} present in the org's `llgenie/` container packages (buildcache tags only)."""
    found: dict[str, list[str]] = {}
    for pkg in _container_packages():
        tags: list[str] = []
        for v in _package_versions(pkg):
            meta = v.get("metadata", {}) or {}
            for t in (meta.get("container", {}).get("tags", []) or []):
                if "buildcache" in t:
                    tags.append(t)
        if tags:
            found[pkg] = sorted(set(tags))
    return found


def orphan_refs() -> list[str]:
    """The fixed-name cache refs that EXIST in the registry but no current producer writes, sorted.

    Only refs whose tag is a fixed cache name (`...buildcache / buildcache-<variant>`) and that are
    NOT in the live producer set are orphans — a live fixed tag is never proposed for deletion.
    """
    reg = registry()
    live = live_cache_refs()
    orphans: set[str] = set()
    for pkg, tags in _existing_tags().items():
        for tag in tags:
            ref = f"{reg}/{pkg}:{tag}"
            if ref not in live:
                orphans.add(ref)
    return sorted(orphans)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Report / sweep superseded fixed-name cache tags (issue #2914)")
    ap.add_argument("cmd", choices=["report", "list", "sweep"])
    args = ap.parse_args(argv)

    if args.cmd in ("report", "list"):
        orphans = orphan_refs()
        for ref in orphans:
            print(ref)
        print(f"[cache-orphan] {len(orphans)} orphaned fixed-name cache tag(s)", flush=True)
        return 0

    # sweep: delete each orphan; a live fixed tag is never in `orphans`, so nothing live is removed.
    orphans = orphan_refs()
    if not orphans:
        print("[cache-orphan] no orphans to sweep", flush=True)
        return 0
    for ref in orphans:
        from proc import run_text
        reg = registry()
        pkg, _, tag = ref[len(f"{reg}/"):].partition(":")
        print(f"[cache-orphan] delete {ref}", flush=True)
        esc = urllib.parse.quote(pkg, safe="")
        for v in _package_versions(pkg):
            meta = v.get("metadata", {}) or {}
            if tag in (meta.get("container", {}).get("tags", []) or []):
                version_id = v["id"]
                run_text(["gh", "api", "--method", "DELETE",
                          "/orgs/%s/packages/container/%s/versions/%s" % (owner(), esc, version_id)])
                break
    print(f"[cache-orphan] deleted {len(orphans)} orphaned fixed-name cache tag(s)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
