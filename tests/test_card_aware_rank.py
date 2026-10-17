"""Issue #225: a t/s figure is compared to THIS host's card, not just its backend.

A backend class (CUDA vs ROCm) is not a card class. A figure measured on a card
bigger than this host's — or on a datacenter part — does not describe this host,
so it must not be presented as a fit (`same_hw`) nor rank above a figure proven
on this card's class. The card comes from the registry's own `hardware` string,
and the strings/VRAM numbers are trending-local-llms' (its README: "a
measurement on a bigger card does not qualify a smaller tier", "datacenter parts
never count"). All cases here are hermetic: a synthetic registry plus the
vendored one; nothing touches a GPU, a container or the network.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import model_engine_pick as mp  # noqa: E402


def _model(engines, mid="fixture-model"):
    return {"id": mid, "name": "Fixture Model", "vram_tier": "16GB", "engines": engines}


def _row(engine, tps, hardware, **kw):
    return {"engine": engine, "tps": tps, "hardware": hardware, "quant": kw.get("quant", ""),
            "date": kw.get("date", "2026-10-13")}


def test_measurement_card_gb_reads_the_hardware_string():
    # Given the hardware strings the registry carries (upstream's shapes)
    cases = [
        ("RTX 5090", 32.0),
        ("RTX 3090 24GB", 24.0),
        ("2x RTX 4090", 48.0),
        ("2x Radeon AI PRO R9700 32GB", 64.0),
        ("RTX 4090 Laptop", 16.0),          # the laptop entry wins over the bare 4090
        ("RTX 4060 8GB laptop (25 GPU layers, rest CPU/RAM), Intel i7-12700H", 8.0),
        ("RX 9070 XT 16GB", 16.0),
        ("8GB GPU", 8.0),
        ("RTX 5060 Ti 16GB", 16.0),
        ("4GB VRAM + 32GB system RAM (MoE/quantized build, partial offload)", 4.0),
        ("Ryzen 5950X 16C/32T CPU (n-cpu-moe=32) + RTX 3090 24GB, 64GB RAM", 24.0),
        ("Radeon 8060S / Strix Halo 128GB (Ryzen AI Max+ 395)", 128.0),
        ("DGX Spark", None),                # a box, not a card: it names no VRAM
        ("GPU serving test (vLLM)", None),
        ("M5 Max (Apple Silicon)", None),
        ("4x NVIDIA GB300 (TP4/EP4), datacenter", None),   # 'GB300' is not a 'NN GB' card
    ]

    # When each is read
    got = [(hw, mp.measurement_card_gb(hw)) for hw, _want in cases]

    # Then the card is the explicit 'NN GB' when stated, else the known card model,
    # and a hardware that names no card yields None
    assert got == cases


def test_datacenter_hardware_names_never_count():
    # Given datacenter and consumer hardware strings
    datacenter = ["single NVIDIA B300 GPU (datacenter)", "4x NVIDIA GB300 (TP4/EP4), datacenter",
                  "NVIDIA H100", "2x A100 80GB", "AMD Instinct MI300X", "MI325X", "TPU v5e", "Gaudi 3"]
    consumer = ["RTX 4090 24GB", "RTX 5060 Ti 16GB", "NVIDIA GB10 (DGX Spark class, 4 concurrent generations)",
                "Radeon 8060S / Strix Halo 96GB (Bosgame M5)", "8GB GPU", "Ryzen AI Max+ 395",
                "M5 Max (Apple Silicon)", "CPU (no GPU), 8GB RAM"]

    # When each is classified
    # Then a datacenter part never counts and a consumer string never does
    assert all(mp.datacenter_hardware(hw) for hw in datacenter)
    assert not any(mp.datacenter_hardware(hw) for hw in consumer)


def test_a_figure_proven_on_this_card_class_ranks_first():
    # Given one engine with a fast figure on a 24 GB card and a slower one on a 12 GB card
    m = _model([_row("llama.cpp", "140", "RTX 3090 24GB"),
                _row("llama.cpp", "97", "RTX 5070 12GB")])

    # When the model is ranked for a 16 GB CUDA card
    rows = mp.rank_engines(m, "cuda", gb=16)

    # Then the figure proven on this card class is the row kept for that engine
    assert len(rows) == 1 and rows[0]["id"] == "llama.cpp"
    assert rows[0]["tps"] == 97 and rows[0]["card_gb"] == 12
    assert rows[0]["rank"] == 0 and rows[0]["same_hw"] and rows[0]["card_class"] == "proven"

    # And on a 24 GB card the 24 GB figure is the proven one instead
    assert mp.rank_engines(m, "cuda", gb=24)[0]["tps"] == 140


def test_a_figure_from_a_bigger_card_is_labelled_and_down_ranked():
    # Given a model whose only CUDA figure ran on a 48 GB box, plus a consumer ROCm figure
    m = _model([_row("vLLM", "300", "2x RTX 4090"),
                _row("Strata", "96", "RX 9070 XT 16GB")])

    # When it is ranked for a 16 GB CUDA card
    rows = {r["id"]: r for r in mp.rank_engines(m, "cuda", gb=16)}

    # Then the bigger-card figure is not a fit, it is labelled, and it is ranked after
    # the proven-class rule can only be satisfied by a comparable card
    assert not rows["vllm"]["same_hw"] and rows["vllm"]["rank"] == 1
    assert rows["vllm"]["card_class"] == "bigger" and rows["vllm"]["card_gb"] == 48
    assert mp.tps_label(rows["vllm"]) == "300 t/s (CUDA, 48 GB card)"

    # And the other-backend figure still ranks below a same-backend one (issue #225 acceptance)
    assert rows["strata"]["rank"] == 3 and mp.tps_label(rows["strata"]) == "96 t/s (ROCm)"
    assert [r["id"] for r in mp.rank_engines(m, "cuda", gb=16)] == ["vllm", "strata"]


def test_a_datacenter_figure_ranks_below_every_consumer_figure():
    # Given a 21 000 t/s datacenter figure, a consumer CUDA figure and a consumer AMD one
    m = _model([_row("vLLM", "21000", "single NVIDIA B300 GPU (datacenter)"),
                _row("llama.cpp", "40", "RTX 3060 12GB"),
                _row("Ollama", "60", "RX 9070 XT 16GB")])

    # When the model is ranked for a 16 GB CUDA card
    rows = mp.rank_engines(m, "cuda", gb=16)
    by_id = {r["id"]: r for r in rows}

    # Then the consumer figure on a comparable card is the fit, by id
    assert rows[0]["id"] == "llama.cpp" and rows[0]["same_hw"] and rows[0]["card_gb"] == 12

    # And the datacenter row is last, labelled, below even the consumer AMD figure
    assert by_id["vllm"]["rank"] == 4 and by_id["vllm"]["card_class"] == "datacenter"
    assert not by_id["vllm"]["same_hw"]
    assert mp.tps_label(by_id["vllm"]) == "21000 t/s (CUDA, datacenter)"
    assert [r["id"] for r in rows] == ["llama.cpp", "ollama", "vllm"]

    # And no row presented as a fit names a datacenter part
    assert not any(r["same_hw"] and mp.datacenter_hardware(r["hardware"]) for r in rows)


def test_no_card_class_keeps_the_backend_ranking():
    # Given a host whose card class is unknown (Apple Silicon, a CPU host, or no card)
    m = _model([_row("vLLM", "300", "2x RTX 4090"),
                _row("llama.cpp", "67", "DGX Spark"),
                _row("Ollama", "96", "RX 9070 XT 16GB")])

    # When the model is ranked for a CUDA host with no card size known
    rows = {r["id"]: r for r in mp.rank_engines(m, "cuda")}

    # Then the backend rule alone decides: every CUDA figure is a fit again, ordered by t/s
    assert [r["id"] for r in mp.rank_engines(m, "cuda")] == ["vllm", "llama.cpp", "ollama"]
    assert rows["vllm"]["same_hw"] and rows["llama.cpp"]["same_hw"] and rows["llama.cpp"]["rank"] == 0
    assert rows["ollama"]["rank"] == 3 and not rows["ollama"]["same_hw"]

    # And a Metal host is a no-card host too: its figures are ranked by backend alone
    mac = _model([_row("MLX", "101", "M5 Max 128GB")])
    assert mp.rank_engines(mac, "metal")[0]["same_hw"]


def test_tps_label_says_where_the_figure_came_from():
    # Given one row per rank the ranking can produce
    cases = [
        ({"tps": 124, "measured_on": "CUDA", "same_hw": True, "card_class": "proven", "card_gb": 12.0}, "124 t/s"),
        ({"tps": 300, "measured_on": "CUDA", "same_hw": False, "card_class": "bigger", "card_gb": 48.0},
         "300 t/s (CUDA, 48 GB card)"),
        ({"tps": 67, "measured_on": "CUDA", "same_hw": False, "card_class": "unknown", "card_gb": None},
         "67 t/s (CUDA, card unknown)"),
        ({"tps": 21000, "measured_on": "CUDA", "same_hw": False, "card_class": "datacenter", "card_gb": None},
         "21000 t/s (CUDA, datacenter)"),
        ({"tps": 96, "measured_on": "ROCm", "same_hw": False, "card_class": "", "card_gb": 16.0}, "96 t/s (ROCm)"),
        ({"tps": 0, "measured_on": "", "same_hw": False, "card_class": "", "card_gb": None}, "supported"),
    ]

    # When each row is labelled
    got = [mp.tps_label(e) for e, _want in cases]

    # Then the text says which card the figure came from
    assert got == [want for _e, want in cases]


def test_the_trend_list_server_is_card_aware():
    # Given the vendored registry
    reg = mp.load_registry()

    # When the trend list is built for a 16 GB CUDA card and for a 48 GB one
    small = {r["model"]["id"]: r["engines"][0] for r in mp.rank_models(reg, "cuda", 16)}
    large = {r["model"]["id"]: r["engines"][0] for r in mp.rank_models(reg, "cuda", 48)}

    # Then each row's server is the card-aware top engine, with its class recorded
    for gb, rows in ((16, small), (48, large)):
        for mid, eng in rows.items():
            m = next(x for x in reg["models"] if x["id"] == mid)
            assert (eng["id"], eng["tps"]) == (mp.rank_engines(m, "cuda", gb=gb)[0]["id"],
                                               mp.rank_engines(m, "cuda", gb=gb)[0]["tps"])
            assert eng["card_class"] in ("proven", "bigger", "unknown", "datacenter", "")

    # And the card size reaches the choice: a model whose best figure needs 48 GB is not
    # served as the same card class on a 16 GB one
    assert small["qwen3.8-27b"]["same_hw"] and small["qwen3.8-27b"]["card_gb"] <= 16
    assert small["qwen3.8-27b"]["id"] != large["qwen3.8-27b"]["id"] or \
        small["qwen3.8-27b"]["tps"] != large["qwen3.8-27b"]["tps"]


def test_225_acceptance_strata_on_a_16gb_card():
    # Given qwen3.8-flash-next-125b in the vendored registry (2026-10-13)
    m = next(x for x in mp.load_registry()["models"] if x["id"] == "qwen3.8-flash-next-125b")

    # When it is ranked for a 16 GB CUDA card
    rows = mp.rank_engines(m, "cuda", gb=16)
    top = rows[0]

    # Then the top engine is justified by a figure measured on a comparable card
    assert top["id"] == "strata" and top["tps"] == 97.3
    assert top["card_gb"] == 12 and top["same_hw"] and top["card_class"] == "proven"
    assert mp.tps_label(top) == "97 t/s"

    # And the out-of-class figures are labelled and ranked below it, read by engine id
    by_id = {r["id"]: r for r in rows}
    assert by_id["tensorfold"]["card_class"] == "unknown"          # DGX Spark names no card
    assert by_id["tensorfold"]["rank"] > top["rank"]
    assert mp.tps_label(by_id["tensorfold"]) == "67 t/s (CUDA, card unknown)"
    assert mp.tps_label(by_id["llama.cpp"]) == "34 t/s (CUDA, 24 GB card)"

    # And no row claims a fit on a card bigger than this host's
    assert not any(r["same_hw"] and (r["card_gb"] or 0) > 16 for r in rows)


@pytest.mark.parametrize("vram", [8, 12, 16, 24, 48])
def test_every_rank_a_row_can_hold_is_documented(vram):
    # Given the vendored registry and a card size
    reg = mp.load_registry()

    # When every model's engines are ranked for that card
    rows = [e for m in reg["models"] for e in mp.rank_engines(m, "cuda", gb=vram)]

    # Then each row carries a documented rank/class pair and is ordered by (rank, -tps)
    assert {r["rank"] for r in rows} <= {0, 1, 2, 3, 4, 5}
    for r in rows:
        assert (r["rank"] == 0) == r["same_hw"] == (r["card_class"] == "proven")
        assert bool(r["card_class"]) == (bool(r["measured_on"]) and r["rank"] != 3)
    for m in reg["models"]:
        keys = [(e["rank"], -e["tps"]) for e in mp.rank_engines(m, "cuda", gb=vram)]
        assert keys == sorted(keys)
