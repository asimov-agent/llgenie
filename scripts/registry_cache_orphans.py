#!/usr/bin/env python3
"""Registry hygiene: find and remove the superseded fixed-name buildx cache tags (issue #2914).

Two changes retired every fixed-name cache namespace this repo used:
- #2891 / PR #2912: engine cells and bases moved from
  `llgenie/<engine>:buildcache-<variant>` and `llgenie/base-<backend>:buildcache`
  to the content-keyed `<full tag>-buildcache`.
- #2911 / PR #2915: helper images moved from `llgenie/<name>:buildcache` to
  `llgenie/<name>:<12hex-tag>-buildcache`.

The fixed tags those builds pushed before the switch remain in GHCR as orphaned
cache layers — no live producer writes them anymore. This script derives the
candidate set from the same repo constants that name live images (so a new
engine or helper is covered the moment it enters params/ or ci_images.IMAGES),
proves each candidate exists, and `gc` deletes exactly those versions — never a
content-keyed ref, never a non-cache tag.

  python3 scripts/registry_cache_orphans.py report [--json]
  python3 scripts/registry_cache_orphans.py gc --yes        # explicit only; never in CI
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ci_images  # noqa: E402
import engine_image  # noqa: E402
import engine_skills  # noqa: E402
from proc import ProcError, run_checked, run_ok  # noqa: E402

# The exact fixed-name cache tag shapes the retired schemes wrote. A content-keyed
# tag (`<pin>-<digest>-<variant>-buildcache`) must NEVER match this.
ORPHAN_TAG_RE = re.compile(r"^buildcache(-[a-z0-9]+)?$")

# `docker buildx imagetools inspect` aligns its header as `Digest:    sha256:...`
# (colon then padding spaces), and older tool versions wrote `digest: sha256:...`
# (single space). Both resolve here; a content digest is always 64 hex chars.
_DIGEST_RE = re.compile(r"digest:\s*(sha256:[0-9a-fA-F]{16,})", re.IGNORECASE)


def candidate_refs() -> list[str]:
    """Every fixed-name cache ref the two retired schemes could have pushed.

    Derived from the live repo constants (ci_images.IMAGES, engine_skills backends,
    the engine params matrix), so the sweep tracks the registry's real population.
    """
    registry = ci_images.registry()
    refs: list[str] = []
    # helper seam (#2911): llgenie/<name>:buildcache
    for name in ci_images.IMAGES:
        refs.append(f"{registry}/llgenie/{name}:buildcache")
    # base seam (#2891): llgenie/base-<backend>:buildcache
    for backend in engine_skills.BACKENDS:
        refs.append(f"{registry}/llgenie/base-{backend}:buildcache")
    # engine cell seam (#2891): llgenie/<engine>:buildcache-<variant>
    for cell in engine_image.matrix():
        pkg = f"llgenie/{cell['engine'].replace('.', '-')}"
        refs.append(f"{registry}/{pkg}:buildcache-{cell['variant']}")
    return sorted(set(refs))


def assert_orphan(ref: str) -> None:
    """Refuse anything that is not a fixed-name cache tag — a live ref never passes."""
    tag = ref.rsplit(":", 1)[-1]
    if not ORPHAN_TAG_RE.match(tag):
        raise SystemExit(f"[registry-cache-orphans] refused: {ref} is not a fixed-name cache tag")


def ref_exists(ref: str) -> bool:
    out = run_ok(["docker", "manifest", "inspect", ref])
    text = (out.stdout + out.stderr).lower()
    if "manifest unknown" in text or "denied" in text:
        return False
    return out.returncode == 0


def split_ref(ref: str) -> tuple[str, str]:
    """(owner, package) of a cache ref like `ghcr.io/asimov-agent/llgenie/test:buildcache`.

    `registry()` carries no scheme by default, but one may be configured, so the
    parse drops it rather than assuming segment counts.
    """
    path = ref.split("://")[-1]
    parts = path.split("/")
    owner = parts[1]
    pkg_parts = parts[2:]
    pkg_parts[-1] = pkg_parts[-1].rsplit(":", 1)[0]  # drop the tag
    return owner, "/".join(pkg_parts)


def _extract_digest(ref: str, text: str) -> str:
    """Resolve the digest from imagetools inspect output, or refuse with the canonical msg."""
    m = _DIGEST_RE.search(text)
    if not m:
        raise SystemExit(f"[registry-cache-orphans] no digest for {ref}")
    return m.group(1)


def digest_of(ref: str) -> str:
    out = run_ok(["docker", "buildx", "imagetools", "inspect", ref])
    return _extract_digest(ref, out.stdout + out.stderr)


def version_id_for(ref: str, digest: str) -> int:
    """GHCR versions carry the DIGEST as the version name; the tag rides on metadata."""
    owner, pkg = split_ref(ref)
    encoded = pkg.replace("/", "%2F")
    out = run_ok(["gh", "api", f"users/{owner}/packages/container/{encoded}/versions?per_page=100",
                  "--jq", f'.[] | select(.name == "{digest}") | .id'])
    raw = out.stdout.strip()
    if not raw:
        raise SystemExit(f"[registry-cache-orphans] no GHCR version for {ref} ({digest})")
    return int(raw.splitlines()[0])


def delete_version(owner: str, pkg: str, version: int) -> None:
    encoded = pkg.replace("/", "%2F")
    try:
        run_checked(["gh", "api", "-X", "DELETE",
                     f"users/{owner}/packages/container/{encoded}/versions/{version}"])
    except ProcError as exc:
        raise SystemExit(f"[registry-cache-orphans] delete failed for {pkg}@{version}: {exc}")


def run_report(checker=ref_exists) -> list[str]:
    orphans = [ref for ref in candidate_refs() if checker(ref)]
    for ref in orphans:
        print(f"orphan: {ref}")
    print(f"orphaned fixed-name cache tags: {len(orphans)}")
    return orphans


def run_gc(checker=ref_exists, deleter=delete_version, version_lookup=version_id_for,
           digest_resolver=digest_of, assume_yes: bool = False) -> int:
    orphans = [ref for ref in candidate_refs() if checker(ref)]
    if not orphans:
        print("orphaned fixed-name cache tags: 0 — nothing to delete")
        return 0
    if not assume_yes:
        print(f"[registry-cache-orphans] {len(orphans)} orphan(s); re-run with --yes to delete")
        for ref in orphans:
            print(f"  would delete: {ref}")
        return 1
    failed = 0
    for ref in orphans:
        assert_orphan(ref)
        owner, pkg = split_ref(ref)
        try:
            deleter(owner, pkg, version_lookup(ref, digest_resolver(ref)))
        except (SystemExit, ProcError) as exc:
            print(f"FAILED {ref}: {exc}")
            failed += 1
    remaining = [ref for ref in orphans if checker(ref)]
    print(f"deleted {len(orphans) - failed}; remaining verified orphans: {len(remaining)}")
    return 0 if not remaining and not failed else 2


def main() -> None:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("mode", choices=["report", "gc"])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--yes", action="store_true", help="perform the deletions (explicit only; never in CI)")
    args = ap.parse_args()
    if args.mode == "report":
        orphans = run_report()
        if args.json:
            print(json.dumps({"orphans": orphans}, indent=2))
        sys.exit(0)
    sys.exit(run_gc(assume_yes=args.yes))


if __name__ == "__main__":
    main()
