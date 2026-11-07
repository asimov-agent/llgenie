"""The default-range VRAM scope filter (OpenSpec vram-range-scope-view, issue
#227): llgenie keeps the full vendored `data/models.json` verbatim and narrows
its VIEW to the VRAM band it targets (default 8–48 GB consumer/workstation).

The filter is a pure function `(registry, range) -> sub-registry`: out-of-band
rows are excluded from the returned view but NEVER dropped from the input (and
never from the file), and reappear when a range includes them. A CPU/Apple-only
row (a non-numeric `vram_tier`, e.g. `CPU`) has no discrete-slot VRAM tier and
is always in scope. The consumers (`trend_list`, `recommend`, `offer`,
`matrix`, `rank_models`) each read the scoped view through `vram_range`.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import model_engine_pick as mp  # noqa: E402


def _model(id_, tier, vram_min=None, num_min=True):
    m = {"id": id_, "name": id_, "type": "LLM", "params": "9B",
         "hf": f"Org/{id_}", "vram_tier": tier,
         "formats": [{"name": "GGUF", "hf": f"Org/{id_}"}],
         "engines": [{"engine": "llama.cpp", "tps": "10", "hardware": "RTX 3060 12GB"}],
         "supported_engines": ["llama.cpp"], "last_seen": "2026-10-09",
         "engagement": {"trend_score": 1.0, "posts_7d": 1}}
    if vram_min is not None:
        m["vram_min"] = vram_min
    return m


def _registry():
    """A registry spanning every band the issue names: the 128 GB Apple MLX entry,
    a 2 GB phone entry, a 8 GB and a 48 GB in-band consumer entry, and a pure-CPU row."""
    return {"generated_utc": "2026-10-31T00:00:00Z", "models": [
        _model("cyber-frost-3.8-mlx", "128GB", "64GB"),      # above default band
        _model("deepseek-r1-1.5b", "2GB", "1GB"),            # below default band
        _model("gemma-4-e2b", "2GB", "2GB"),                 # below default band
        _model("qwen3-8b", "8GB", "4GB"),                    # in band
        _model("qwen3.8-flash-next-125b", "48GB", "48GB"),   # in band (top edge)
        _model("kolibri-1", "CPU", "CPU"),                   # CPU-only: always in scope
    ]}


def test_default_scope_excludes_out_of_band_and_keeps_the_file_intact():
    # Given the full registry (the "vendored file")
    reg = _registry()
    all_ids = [m["id"] for m in reg["models"]]

    # When scope_models runs with the DEFAULT consumer band
    scoped = mp.scope_models(reg)

    # Then in-band rows are present
    names = [m["id"] for m in scoped["models"]]
    assert "qwen3-8b" in names
    assert "qwen3.8-flash-next-125b" in names
    # And the 128 GB / 2 GB entries are absent from the VIEW
    assert "cyber-frost-3.8-mlx" not in names
    assert "deepseek-r1-1.5b" not in names
    assert "gemma-4-e2b" not in names
    # And the pure-CPU row is always in scope (its tier is non-numeric)
    assert "kolibri-1" in names

    # And nothing was dropped from the input (filtered, not dropped)
    assert [m["id"] for m in reg["models"]] == all_ids


def test_scope_wide_range_includes_the_out_of_band_entry():
    # Given the full registry
    reg = _registry()

    # When a wide range includes the 128 GB Apple entry
    scoped = mp.scope_models(reg, (8.0, 512.0))

    # Then the 128 GB entry reappears (filtered is not dropped)
    names = [m["id"] for m in scoped["models"]]
    assert "cyber-frost-3.8-mlx" in names


def test_scope_narrow_low_range_includes_the_2gb_entry():
    # Given the full registry
    reg = _registry()

    # When a range includes the 2 GB tier (a phone box)
    scoped = mp.scope_models(reg, (2.0, 48.0))

    # Then the 2 GB entries reappear
    names = [m["id"] for m in scoped["models"]]
    assert "deepseek-r1-1.5b" in names
    assert "gemma-4-e2b" in names


def test_scope_is_a_pure_function_of_registry_and_range():
    # Given a registry
    reg = _registry()

    # When scope_models is called with two different ranges
    a = mp.scope_models(reg, (8.0, 48.0))
    b = mp.scope_models(reg, (8.0, 512.0))

    # Then each is a stable function of (registry, range) — same args, same result
    assert mp.scope_models(reg, (8.0, 48.0)) == a
    assert mp.scope_models(reg, (8.0, 512.0)) == b
    # And the result is a fresh dict, never the input's models list identity
    assert a is not reg and a["models"] is not reg["models"]
    # And a CPU-only row is in scope for ANY range
    for rng in ((8.0, 48.0), (8.0, 512.0), (0.5, 2.0)):
        assert "kolibri-1" in [m["id"] for m in mp.scope_models(reg, rng)["models"]]


def test_model_in_scope_is_the_single_predicate():
    # Given the registry
    reg = _registry()

    # Then model_in_scope agrees with scope_models membership for every (model, range)
    for rng in ((8.0, 48.0), (8.0, 512.0), (2.0, 64.0)):
        scoped = mp.scope_models(reg, rng)
        want = {m["id"] for m in scoped["models"]}
        got = {m["id"] for m in reg["models"] if mp.model_in_scope(m, rng)}
        assert got == want


def test_consumers_read_the_scoped_view(tmp_path, monkeypatch):
    # Given a registry and the engine set
    reg = _registry()
    monkeypatch.setattr(mp, "engine_ids", lambda: {"llama.cpp": {"id": "llama-cpp",
                                                                 "formats": ["gguf"],
                                                                 "variants": ["cuda", "cpu"]}})
    monkeypatch.setattr(mp, "_tree", lambda repo, revision="main": [])
    monkeypatch.setenv("LLGENIE_QUANT_CATALOG", "0")

    # When a consumer runs with the DEFAULT band (a 64 GB card, so out-of-band rows would fit)
    tl = mp.trend_list(reg, 64, ram_gb=64, arch="cuda")
    tl_ids = [m["id"] for m in tl]

    # Then the 128 GB entry and the 2 GB entries are NOT in the default view
    assert "cyber-frost-3.8-mlx" not in tl_ids
    assert "deepseek-r1-1.5b" not in tl_ids
    assert "gemma-4-e2b" not in tl_ids

    # And when the SAME consumer widens the range, the out-of-band entries enter again
    wide = mp.trend_list(reg, 64, ram_gb=64, arch="cuda", vram_range=(8.0, 512.0))
    assert "cyber-frost-3.8-mlx" in [m["id"] for m in wide]

    # And the consumers that funnel through trend_list read the same view
    assert "cyber-frost-3.8-mlx" not in [r["model"]["id"] for r in
                                         mp.rank_models(reg, "cuda", 64, vram_range=None)]
    assert "cyber-frost-3.8-mlx" not in [m["id"] for m in
                                         [r["model"] for r in mp.recommend(reg, "cuda", 64, ram_gb=64)]]


def test_vram_range_env_override_widens_the_default(monkeypatch):
    # Given a malformed or absent override
    monkeypatch.delenv("LLGENIE_VRAM_RANGE", raising=False)
    assert mp.effective_vram_range() == mp.DEFAULT_VRAM_RANGE

    # When a big-box override is set
    monkeypatch.setenv("LLGENIE_VRAM_RANGE", "8, 512")
    assert mp.effective_vram_range() == (8.0, 512.0)

    # Then an explicit range always wins over the env
    assert mp.effective_vram_range((8.0, 48.0)) == (8.0, 48.0)

    # And a malformed override falls back to the default, never crashes
    monkeypatch.setenv("LLGENIE_VRAM_RANGE", "garbage")
    assert mp.effective_vram_range() == mp.DEFAULT_VRAM_RANGE


def test_the_vendored_file_is_never_changed_by_scoping():
    # Given the REAL vendored store
    reg = mp.load_registry()
    all_before = [m["id"] for m in reg["models"]]

    # When the default view is computed
    scoped = mp.scope_models(reg)

    # Then the vendored store still has every model (read-time view, not a sync-time drop)
    assert len(scoped["models"]) <= len(reg["models"])
    assert [m["id"] for m in reg["models"]] == all_before
    assert len(scoped["models"]) > 0


def test_the_real_128gb_and_2gb_entries_are_out_of_the_default_view():
    # Given the REAL vendored store
    reg = mp.load_registry()
    names = [m["id"] for m in mp.scope_models(reg)["models"]]

    # Then the named out-of-band entries are in the file but filtered from the default view
    all_ids = {m["id"] for m in reg["models"]}
    assert "cyber-frost-3.8-mlx" in all_ids          # present in the file
    assert "cyber-frost-3.8-mlx" not in names        # filtered from the default view
    assert next((m for m in reg["models"] if m["id"] == "deepseek-r1-1.5b"), None) is not None
    assert "deepseek-r1-1.5b" not in names

    # And the 128 GB entry reappears when the range includes its tier
    wide = [m["id"] for m in mp.scope_models(reg, (8.0, 512.0))["models"]]
    assert "cyber-frost-3.8-mlx" in wide
