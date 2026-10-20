#!/usr/bin/env python3
"""The registry's stated footprint is read, not ignored (MODEL_CONTRACT.md, issue #414).

`data/models.json` states what a run needs — `weight_gb`, `context_tokens`, `system_ram_min`,
`storage_offload`, `engine_min_version` — on the model AND on an individual `engines[]`
measurement ("the footprint of that run", per the contract). llgenie used to budget from
`vram_tier` and a file-size guess alone, which is the difference between "fits" and "OOMs at
128k context".

These tests drive the real functions (`footprint`, `stated_gb`, `stated_context`, `fits`,
`trend_list`, `rank_engines`, `_no_fit_reason`) and the real guard (`registry_keys.compare`)
against fixture registries — no network, no Hub, no model files.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import model_engine_pick as MP  # noqa: E402
import registry_keys as RK  # noqa: E402

#: Every engine the picker can offer needs an image in the binaries file, so this fixture uses
#: one engine that exists there: llama.cpp.
MODEL = {
    "id": "fixture-model", "name": "Fixture Model", "full_name": "Fixture Model",
    "type": "LLM", "formats": [{"name": "GGUF", "hf": "org/fixture-gguf"}],
    "license": "Apache 2.0", "params": "27B", "hf": "org/fixture-gguf",
    "vram_tier": "24GB", "vram_min": "16GB",
    "backends": ["CUDA"], "supported_engines": ["llama.cpp"],
    "engines": [{"engine": "llama.cpp", "tps": "40", "hardware": "RTX 4090 24GB",
                 "quant": "Q4_K_M", "date": "2026-10-18"}],
    "why": "fixture", "engagement": {"likes": 10, "comments": 1, "views": 100},
    "last_seen": "2026-10-18",
}


def registry(model: dict) -> dict:
    return {"generated_utc": "2026-10-19T19:24:53Z", "note": "fixture",
            "engines": {"llama.cpp": {"backend": "CUDA / CPU", "note": "fixture",
                                      "url": "https://github.com/ggml-org/llama.cpp"}},
            "models": [model]}


# --------------------------------------------------------------------------- the parsing
def test_a_stated_size_is_read_as_gb_and_never_invented():
    """`weight_gb` / `system_ram_min` are prose-bearing strings in the store."""
    # Given the shapes the contract shows
    cases = {"5.95GB Q4_K_M": 5.95, "16GB": 16.0, "640GB NVMe, experts on SSD": 640.0,
             "800MB": 0.78, 12: 12.0}

    # When  each is read as a size
    # Then  the first number wins, MB converts, and an empty string invents nothing
    for stated, want in cases.items():
        assert MP.stated_gb(stated) == want, stated
    assert MP.stated_gb("") is None
    assert MP.stated_gb(None) is None
    assert MP.stated_gb("experts streamed from SSD") is None


def test_a_stated_context_is_read_in_tokens():
    """`context_tokens` is '131072', '128K' or '1M' depending on the source post."""
    # Given the spellings a source post may use
    # When  the window is read
    # Then  each lands on the same token count a launcher would use
    assert MP.stated_context("131072") == 131072
    assert MP.stated_context("128K") == 131072
    assert MP.stated_context("1M") == 1048576
    assert MP.stated_context(32768) == 32768
    assert MP.stated_context("no idea") is None


# --------------------------------------------------------------------------- the footprint
def test_the_measurement_footprint_wins_over_the_model_one():
    """The contract states a run's own footprint inside the measurement; that value wins."""
    # Given a model that states a footprint, and one measurement that states its own
    model = dict(MODEL)
    model.update({"weight_gb": "9.2GB Q4_K_M", "context_tokens": "32768",
                  "system_ram_min": "32GB"})
    model["engines"] = [{"engine": "llama.cpp", "tps": "40", "hardware": "RTX 4090 24GB",
                         "weight_gb": "5.95GB Q4_K_M", "context_tokens": "131072"}]

    # When  the footprint of that measurement is read, and of the model alone
    per_run = MP.footprint(model, model["engines"][0])
    whole = MP.footprint(model)

    # Then  the measurement's own values win, the model's fill the gaps, and nothing is invented
    assert per_run["weight_gb"] == "5.95GB Q4_K_M"
    assert per_run["context_tokens"] == "131072"
    assert per_run["system_ram_min"] == "32GB"
    assert whole["weight_gb"] == "9.2GB Q4_K_M"
    assert "engine_min_version" not in whole, "an absent field is a data gap, not a default"
    assert MP.stated_budget_gb(model, model["engines"][0]) == 5.95


# --------------------------------------------------------------------------- the fit decision
def test_a_stated_system_ram_floor_excludes_the_model():
    """`system_ram_min` is a hard floor: more VRAM cannot make up for too little RAM."""
    # Given a model that states it needs 64GB of system RAM
    model = dict(MODEL, system_ram_min="64GB")

    # When  the card fits (24GB card, 24GB tier) but this host has only 32GB of RAM
    fits_plenty = MP.fits(model, 24, 128)
    fits_short = MP.fits(model, 24, 32)

    # Then  the RAM floor is what excludes it, and a host above it still fits
    assert fits_plenty is True
    assert fits_short is False


def test_no_stated_ram_keeps_the_previous_behaviour():
    """A store that states nothing must behave exactly as before (never invented)."""
    # Given a model with no footprint fields at all
    model = dict(MODEL)

    # When  the fit is asked for with any amount of RAM
    # Then  only the VRAM column decides, as before
    assert MP.fits(model, 24, 8) is True
    assert MP.fits(model, 8, 256) is False


def test_the_trend_list_drops_a_model_whose_stated_ram_is_above_this_host():
    """`trend_list` is the list plain `llgenie` prints: the RAM floor applies there too."""
    # Given a registry whose only model states a 64GB system-RAM requirement
    reg = registry(dict(MODEL, system_ram_min="64GB"))

    # When  the list is built for this card with 32GB of RAM, and with 128GB
    short = MP.trend_list(reg, 24, 32)
    enough = MP.trend_list(reg, 24, 128)

    # Then  the model is absent on the small host and present on the large one
    assert short == []
    assert [m["id"] for m in enough] == ["fixture-model"]


# --------------------------------------------------------------------------- the printed row
def test_an_engine_row_carries_the_measurements_own_footprint():
    """The pick prints per engine, so the footprint must travel with the engine row."""
    # Given a model whose single measurement states weight, context and a required build
    model = dict(MODEL, weight_gb="9.2GB Q4_K_M")
    model["engines"] = [{"engine": "llama.cpp", "tps": "40", "hardware": "RTX 4090 24GB",
                         "weight_gb": "5.95GB Q4_K_M", "context_tokens": "131072",
                         "engine_min_version": "llama.cpp b6xxx, --n-gpu-layers 99"}]

    # When  the engines are ranked for a 24GB CUDA card
    rows = MP.rank_engines(model, "cuda", MP.engine_ids(), 24)

    # Then  the llama.cpp row states the run's own footprint, not the model's
    row = next(r for r in rows if r["id"] == "llama.cpp")
    assert row["footprint"]["weight_gb"] == "5.95GB Q4_K_M"
    assert MP.stated_context(row["footprint"]["context_tokens"]) == 131072
    assert "b6xxx" in row["footprint"]["engine_min_version"]


def test_the_no_fit_reason_names_the_stated_ram_before_any_file_size(monkeypatch):
    """When the store says the RAM is too small, say that — do not guess from a download."""
    # Given a model that states 64GB of system RAM, and no Hub access (the guess is unavailable)
    model = dict(MODEL, system_ram_min="64GB")
    monkeypatch.setattr(MP, "gguf_weights", lambda repo: [])

    # When  the reason is asked for on a 32GB host
    reason = MP._no_fit_reason(model, ["gguf"], 24, "cuda", 32)

    # Then  it cites the stated floor
    assert "64 GB system RAM" in reason and "32 GB" in reason
    assert "smallest GGUF" not in reason


# --------------------------------------------------------------------------- the guard
def test_a_lowered_stated_footprint_is_a_loss():
    """The additive-only guard covers the footprint scalars, like t/s and engagement."""
    # Given a registry that states a weight, a context and a RAM floor
    prev = registry(dict(MODEL, weight_gb="9.2GB Q4_K_M", context_tokens="131072",
                         system_ram_min="32GB"))
    # When  a sync restates each one smaller
    cur = registry(dict(MODEL, weight_gb="5.95GB Q4_K_M", context_tokens="32768",
                        system_ram_min="16GB"))

    # Then  every shrink is a finding, and each names the field
    findings = RK.compare(prev, cur)
    assert any("weight_gb lowered" in f for f in findings), findings
    assert any("context_tokens lowered" in f for f in findings), findings
    assert any("system_ram_min lowered" in f for f in findings), findings


def test_a_grown_or_restated_footprint_is_not_a_loss():
    """Growing is fine, and so is restating the same number in another spelling."""
    # Given a registry that states a footprint
    prev = registry(dict(MODEL, weight_gb="5.95GB Q4_K_M", context_tokens="131072"))

    # When  the sync grows the weight, restates the context and adds a new field
    cur = registry(dict(MODEL, weight_gb="6.4GB Q5_K_M", context_tokens="131072 tokens",
                        system_ram_min="32GB"))

    # Then  nothing is reported
    assert RK.compare(prev, cur) == []


def test_a_measurement_footprint_that_disappears_is_a_loss():
    """A measurement's own footprint is part of the measurement's value (contract issue #337)."""
    # Given a measurement that states the run's weight
    measured = {"engine": "llama.cpp", "tps": "40", "hardware": "RTX 4090 24GB",
                "weight_gb": "5.95GB Q4_K_M"}
    prev = registry(dict(MODEL, engines=[measured]))
    # When  the sync drops the stated weight from that same measurement
    cur = registry(dict(MODEL, engines=[{k: v for k, v in measured.items() if k != "weight_gb"}]))

    # Then  the loss is reported against the measurement
    findings = RK.compare(prev, cur)
    assert any("llama.cpp on RTX 4090 24GB weight_gb lowered" in f for f in findings), findings
