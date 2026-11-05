"""#1723: per-owner high+lower selection must never emit near-identical (32-byte tier)
sizes out of order or as a 'lower' pick. The host acceptance test (tests/test_top_tier_acceptance.py,
which runs on live HF) groups by OWNER (the repo id before the first "/"). discover previously ranked
by full repo id, so an owner with two repos whose best-fit sizes differ by 32 bytes emitted
smaller-before-larger (measured on main: `ccore picks must be high->lower` ->
assert [4482402816, 4482402848] == sorted desc).
"""

from __future__ import annotations

import pytest

import scripts.llgenie_serve as llgenie_serve  # noqa: E402  (same import seam as the sibling hermetic tests)


def _files(*pairs):
    """[(size_bytes, path), ...] -> the dict shape _repo_gguf_files returns."""
    return [{"path": path, "size_bytes": size, "size_gb": size / (1024 ** 3)} for size, path in pairs]


def test_near_identical_sizes_are_not_both_picked_and_never_ascending(monkeypatch):
    """A 32-byte tier boundary must not produce two picks, and never an ascending order."""
    repos = [{"repo": "ccore/A-GGUF", "downloads": 1, "likes": 1, "trendingScore": 300}]
    files_by_repo = {
        "ccore/A-GGUF": _files((4482402848, "A-Q8_0.gguf"), (4482402816, "A-Q4_K_M.gguf")),
    }

    monkeypatch.setattr(llgenie_serve, "_trending_gguf_repos", lambda limit=25: repos)
    monkeypatch.setattr(llgenie_serve, "_repo_gguf_files", lambda repo: files_by_repo[repo])
    monkeypatch.setattr(llgenie_serve, "_probe_file_downloadable", lambda *a, **k: "ok")
    monkeypatch.setattr(llgenie_serve, "MIN_TOP_TIER_GB", 1.0)

    result = llgenie_serve.discover_top_tier(limit=4, total_ram_bytes=48 * 1024 ** 3,
                                             headroom_bytes=3 * 1024 ** 3, min_trending_score=0,
                                             per_provider=2)
    sizes = [c["size_bytes"] for c in result]
    assert sizes == sorted(sizes, reverse=True), f"picks must be high->lower: {sizes}"
    assert len(result) <= 1, f"near-identical sizes must not both be picked: {sizes}"


def test_an_owner_with_two_distinct_tiers_keeps_high_then_lower(monkeypatch):
    """A real high + clearly-lower pair (>=25% apart) is preserved, sorted descending."""
    repos = [{"repo": "orion/Qwen-GGUF", "downloads": 1, "likes": 1, "trendingScore": 300}]
    files_by_repo = {
        "orion/Qwen-GGUF": _files((20 * 1024 ** 3, "Q8_0.gguf"), (12 * 1024 ** 3, "Q4_K_M.gguf")),
    }
    monkeypatch.setattr(llgenie_serve, "_trending_gguf_repos", lambda limit=25: repos)
    monkeypatch.setattr(llgenie_serve, "_repo_gguf_files", lambda repo: files_by_repo[repo])
    monkeypatch.setattr(llgenie_serve, "_probe_file_downloadable", lambda *a, **k: "ok")
    monkeypatch.setattr(llgenie_serve, "MIN_TOP_TIER_GB", 1.0)

    result = llgenie_serve.discover_top_tier(limit=4, total_ram_bytes=48 * 1024 ** 3,
                                             headroom_bytes=3 * 1024 ** 3, min_trending_score=0,
                                             per_provider=2)
    sizes = [c["size_bytes"] for c in result]
    assert sizes == sorted(sizes, reverse=True)
    assert len(sizes) == 2
    assert (sizes[0] - sizes[1]) >= 0.25 * sizes[0]
