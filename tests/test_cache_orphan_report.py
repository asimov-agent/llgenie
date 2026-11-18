"""Hermetic tests for scripts/cache_orphan_report.py (issue #2914).

The report's safety contract: a fixed-name cache tag is an orphan ONLY when it exists in the
registry AND no current producer seam derives it. The live producer set is derived from the ONE
seams the builds write with (`engine_image.cache_ref`, `ci_images.cache_ref`), so that when the
content-hash keying (#2891/#2911) lands and edits those seams, the superseded fixed tags surface as
orphans with no second derivation to keep in sync.

No network, no gh, no docker: the registry enumeration seam (`cache_orphan_report._container_packages`
/ `_package_versions` / `_gh_api`) is stubbed; the producer seams run for real.
"""
from __future__ import annotations

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import cache_orphan_report as cor  # noqa: E402


def _stub_registry(monkeypatch, packages_tags: dict[str, list[str]]) -> None:
    """Point the registry enumeration at a fixed {package: [tags]} table."""
    import cache_orphan_report as c
    monkeypatch.setattr(c, "_container_packages", lambda: sorted(packages_tags))
    tags = dict(packages_tags)

    def versions(pkg: str):
        return _tag_to_versions(tags.get(pkg, []))

    monkeypatch.setattr(c, "_package_versions", versions)
    monkeypatch.setattr(c, "_gh_api", lambda args: [])


def _tag_to_versions(tags: list[str]) -> list[dict]:
    return [{"id": i, "metadata": {"container": {"tags": [t]}}} for i, t in enumerate(tags)]


def test_live_producer_set_covers_helpers_bases_and_cells(tmp_path, monkeypatch):
    """Live refs come from BOTH seams: helper images, engine base Dockerfiles, engine cells."""
    live = cor.live_cache_refs()
    reg = cor.registry()
    # helper image (ci_images.IMAGES)
    assert f"{reg}/llgenie/test:buildcache" in live
    assert f"{reg}/llgenie/openspec:buildcache" in live
    # engine base (every committed backend Dockerfile)
    base_cpu = [r for r in live if r.rsplit(":", 1)[0].endswith("/base-cpu")]
    assert base_cpu and base_cpu[0].endswith(":buildcache")
    # engine cells (committed params -> resolve().tag image name, one cache ref per variant)
    cells = [r for r in live if ":buildcache-" in r]
    assert cells, "no engine cell cache refs derived"


def test_zero_orphans_while_fixed_tags_are_still_live(tmp_path, monkeypatch):
    """At the current head every producer seam still writes the FIXED names, so a registry holding
    exactly the fixed tags reports NO orphans — a sweep would be unsafe and is refused."""
    live = cor.live_cache_refs()
    # the registry mirrors only the live fixed tags (parceled per existing package)
    packages: dict[str, list[str]] = {}
    for ref in sorted(live):
        body, _, tag = ref.partition(":")  # ghcr.io/asimov-agent/llgenie/test
        pkg = body.rsplit("/", 1)[-1]
        packages.setdefault(f"llgenie/{pkg}", []).append(tag)
    _stub_registry(monkeypatch, packages)
    assert cor.orphan_refs() == []


def test_orphan_reported_only_when_tag_has_no_live_producer(tmp_path, monkeypatch):
    """A fixed cache tag present in the registry that NO seam produces is an orphan and is reported."""
    _stub_registry(monkeypatch, {
        "llgenie/some-old-engine": ["buildcache-cuda"],
        "llgenie/test": ["buildcache"],
    })
    orphan = cor.orphan_refs()
    # `llgenie/test:buildcache` is live (ci_images.cache_ref writes it); the old engine's is not.
    lines = [r for r in orphan]
    assert len(lines) == 1
    assert lines[0].endswith("llgenie/some-old-engine:buildcache-cuda")


def test_live_fixed_tag_is_never_proposed_for_sweep(tmp_path, monkeypatch):
    """A fixed tag a current producer still writes is NOT returned as an orphan — the sweep gate."""
    reg = cor.registry()
    _stub_registry(monkeypatch, {
        "llgenie/test": ["buildcache"],  # live helper ref
    })
    orphan = cor.orphan_refs()
    assert all(not r.endswith("llgenie/test:buildcache") for r in orphan)
    ref = f"{reg}/llgenie/test:buildcache"
    assert ref in cor.live_cache_refs()
