"""The committed quant table is the single decider for plan_download's mlx/safetensors
branch (issue-fix quant-catalog seam): a (model, engine) pair the table lists resolves
from the table — never a re-query of the live Hub — and a pair the table does not cover
still falls back to live resolution.

This locks the contract `matrix()` and `llgenie --pick` must agree on for the same
model+card: matrix() offers a cell when the committed table's quant fits the budget;
plan_download (the CLI's download decision) must answer the SAME question through the
SAME committed seam. An upstream repo re-push — a live figure that no longer fits — must
not flip a certified-green pick red, because the table's own sizes are the answer.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import model_engine_pick as mp  # noqa: E402

HERE = Path(__file__).parent


def _catalog_fixture(model_id: str, plan: dict, engine: str = "MLX") -> dict:
    """A minimal committed quant table with one (model, engine) snapshot plan."""
    return {
        "meta": {"generated_utc": "2026-11-15T00:00:00Z", "source": "hermetic-test"},
        "files": {model_id: {engine: {"arch": ["cpu", "cuda", "metal"], "quants": [plan]}}},
    }


def _snapshot_doc(entries: dict) -> dict:
    return {"note": "hermetic diverged-live recording", "trees": entries, "searches": {}, "errors": {}}


def _hub_snapshot(tmp_path: Path, entries: dict, searches: dict) -> Path:
    doc = {"note": "hermetic recording", "trees": entries, "searches": searches, "errors": {}}
    path = tmp_path / "hub.json"
    path.write_text(json.dumps(doc) + "\n")
    return path


def _tree_url(repo: str) -> str:
    return f"{mp.HF}/api/models/{repo}/tree/main?recursive=true"


def _search_url(base: str) -> str:
    import urllib.parse
    return f"{mp.HF}/api/models?search={urllib.parse.quote(base)}&filter=mlx&sort=downloads&direction=-1&limit=50"


def _metal_budget_gb() -> float:
    # weight_budget_gb(24, moe=False, 64, metal): the 24 GB card's weight budget this
    # issue measured (9.8 GB) — the number the live repush no longer fit.
    return mp.weight_budget_gb(24, False, 64, "metal")


def test_catalogued_mlx_model_resolves_from_table_when_live_diverges(tmp_path, monkeypatch):
    """A model+engine listed in the committed table gets the table's plan even when the
    live hub (the recording) reports the same repo too big to fit the card budget — the
    table's quoted size wins, so an upstream re-push cannot flip the pick red."""

    # Given a committed table listing a 24-GB metal card plan for the model at 3.0 GB,
    #   and a matching (model, engine) MLX pair
    model = {"id": "test-quant-model", "name": "Test Quant", "hf": "acme/Test-Quant",
             "engines": [{"engine": "MLX"}], "supported_engines": ["MLX"]}
    repo = "acme/Test-Quant-MLX-3bit"
    plan = {"repo": repo, "revision": "main", "path": "", "dir": True,
            "files": ["config.json", "model.safetensors"], "size_gb": 3.0}
    catalog = _catalog_fixture("test-quant-model", plan)
    catalog_path = tmp_path / "quant-catalog.json"
    catalog_path.write_text(json.dumps(catalog) + "\n")
    monkeypatch.setenv("LLGENIE_QUANT_CATALOG", str(catalog_path))

    #   and a live Hub (recording) where the SAME repo is re-pushed so large (12 GiB)
    #   that it no longer fits the 9.8 GB budget — live resolution would refuse
    assert _metal_budget_gb() < 12.0 < 24.0
    hub = _hub_snapshot(tmp_path, {_tree_url(repo): [["config.json", 1000], ["model.safetensors", int(12 * 2**30)]]}, {})

    # When  the pick plans the model's MLX download on a 24 GB metal card
    with mp.hub_snapshot_file(hub):
        out = mp.plan_download(model, 24, 64, "mlx-safetensors", "metal", engine="mlx")

    # Then  it is the committed table's plan (the repo at its 3.0 GB quoted size), not the
    #       diverged live figure — the table's size wins over the re-pushed live tree
    assert out is not None
    assert out["repo"] == repo
    assert out["dir"] is True
    assert out["size"] / 2**30 == 3.0
    assert out["size"] <= _metal_budget_gb() * 2**30


def test_catalogued_mlx_model_with_only_oversized_table_plan_refuses(tmp_path, monkeypatch):
    """When the pair IS catalogued but the table's own largest plan exceeds the card
    budget, plan_download refuses (returns None) — it never re-queries the live Hub and
    never invents a fit, mirroring engine_supported_quants for a catalogue pair."""

    # Given a committed table whose only MLX plan for the model is 12.0 GB — above the
    #   card's 9.8 GB budget — and a live Hub (recording) reporting a 3.0 GB conversion
    model = {"id": "big-quant-model", "name": "Big Quant", "hf": "acme/Big-Quant",
             "supported_engines": ["MLX"]}
    repo = "acme/Big-Quant-MLX-3bit"
    # the catalog names a plan that would NOT fit; a smaller live repo WOULD fit — the
    # table is authoritative and the CLI must not go looking for a smaller repush
    catalog = _catalog_fixture("big-quant-model",
                               {"repo": "acme/Big-Quant-MLX-heavy", "revision": "main", "path": "",
                                "dir": True, "files": ["config.json", "model.safetensors"], "size_gb": 12.0})
    catalog_path = tmp_path / "big-catalog.json"
    catalog_path.write_text(json.dumps(catalog) + "\n")
    monkeypatch.setenv("LLGENIE_QUANT_CATALOG", str(catalog_path))
    hub = _hub_snapshot(tmp_path, {_tree_url(repo): [["config.json", 1000], ["model.safetensors", int(3 * 2**30)]]},
                        {_search_url("Big-Quant"): [repo]})

    # When  the pick plans the model's MLX download on a 24 GB metal card
    with mp.hub_snapshot_file(hub):
        out = mp.plan_download(model, 24, 64, "mlx-safetensors", "metal", engine="mlx")

    # Then  nothing fits from the table and the pick refuses — it does not fall back to a
    #       live repo the table did not certify
    assert out is None


def test_uncatalogued_model_falls_back_to_live(tmp_path, monkeypatch):
    """A (model, engine) pair the committed table does NOT cover still resolves live —
    the documented fallback is kept (AC2)."""

    # Given a model absent from the committed table, and a live Hub (recording) whose
    #   MLX conversion is 3.0 GB and fits the 24 GB metal card budget
    model = {"id": "other-model", "name": "Other", "hf": "acme/Other", "engines": [{"engine": "MLX"}]}
    catalog_path = tmp_path / "other-catalog.json"
    catalog_path.write_text(json.dumps(_catalog_fixture("test-quant-model", {
        "repo": "acme/Test-Quant-MLX-3bit", "revision": "main", "path": "", "dir": True,
        "files": ["config.json", "model.safetensors"], "size_gb": 3.0})) + "\n")
    monkeypatch.setenv("LLGENIE_QUANT_CATALOG", str(catalog_path))
    repo = "acme/Other-MLX-3bit"
    hub = _hub_snapshot(tmp_path, {_tree_url(repo): [["config.json", 1000], ["model.safetensors", int(3 * 2**30)]]},
                        {_search_url("Other"): [repo]})

    # When  the pick plans the model's MLX download on a 24 GB metal card
    with mp.hub_snapshot_file(hub):
        out = mp.plan_download(model, 24, 64, "mlx-safetensors", "metal", engine="mlx")

    # Then  it resolves LIVE to the recording's fitting snapshot (the fallback is real)
    assert out is not None
    assert out["repo"] == repo
    assert out["dir"] is True
    assert out["size"] <= _metal_budget_gb() * 2**30
