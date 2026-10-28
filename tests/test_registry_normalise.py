#!/usr/bin/env python3
"""The vendored store is normalised on the way in (issue #687).

Upstream's store started writing model names into `formats[].name` — `"Qwen3.8-27B"`,
`"LLM (MoE)"`, `"Bonsai 2 27B (mlx.fast)"` — which is not a format any consumer can act on:
`model_engine_pick` could not map those rows to a download, so the pick/matrix tests saw
`use_format: safetensors` where a GGUF was expected and the planner raised StopIteration.
`sync_registry.normalise()` restricts `formats` to the vocabulary (GGUF | MLX | safetensors |
mlx-safetensors | litertlm) and states a format from the row's own repo/id when upstream names
none, so the vendored file says what llgenie actually does.

NO-SKIP POLICY: a missing prerequisite is a LOUD FAILURE, never a skip.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

from scripts import sync_registry as sr


def _store(*rows: dict) -> dict:
    return {"generated_utc": "2026-10-26T14:06:43Z", "engines": {"llama.cpp": {}},
            "models": list(rows)}


def _row(id_: str, name: str, formats: list[dict], hf: str = "") -> dict:
    return {"id": id_, "name": name, "hf": hf or f"org/{name}", "vram_tier": "16GB",
            "formats": formats, "engines": [{"engine": "llama.cpp", "tps": "10",
                                             "hardware": "RTX 4090",
                                             "source_post": f"https://x/status/{id_}"}]}


# ---------------------------------------------------------------------------
# the formats vocabulary
# ---------------------------------------------------------------------------
def test_a_model_name_in_formats_name_is_restated_as_the_format_the_repo_states():
    """The exact upstream shape: `formats[].name` repeats the model, the repo says GGUF."""

    # Given a row whose only format entry names the model, for a -GGUF repo
    store = _store(_row("qwen3-8b", "Qwen3 8B", [{"name": "Qwen3 8B", "hf": "Q/Qwen3-8B-GGUF"}],
                       hf="Q/Qwen3-8B-GGUF"))

    # When the store is normalised
    out, notes = sr.normalise(store)

    # Then the vendored row states the format its repo publishes, and the change is printed
    assert out["models"][0]["formats"] == [{"name": "GGUF", "hf": "Q/Qwen3-8B-GGUF"}]
    assert any("qwen3-8b" in n and "not formats" in n for n in notes), notes


def test_an_mlx_row_is_restated_as_mlx_from_its_id_or_repo():
    """A per-box MLX conversion keeps saying MLX — never GGUF, which it cannot download."""

    # Given a row whose format name is a recipe label and whose repo has no suffix
    store = _store(_row("qwen3-8b-mlx-run", "Qwen3 8B (MLX run)", [{"name": "Qwen3 8B (MLX run)"}],
                        hf="meta/Llama-3.1-70B-Instruct"))

    # When the store is normalised
    out, _ = sr.normalise(store)

    # Then the format comes from the row's own id, not from a default
    assert out["models"][0]["formats"] == [{"name": "MLX", "hf": "meta/Llama-3.1-70B-Instruct"}]


def test_a_vocabulary_format_is_kept_and_canonicalised():
    """A real format survives, in the vocabulary's spelling, and is not duplicated."""

    # Given a row that states the same format twice in different cases
    store = _store(_row("m1", "Model One", [{"name": "gguf", "hf": "a/m1-gguf"},
                                            {"name": "GGUF", "hf": "a/m1-gguf"}]))

    # When the store is normalised
    out, notes = sr.normalise(store)

    # Then one canonical entry remains and nothing was reported as dropped
    assert out["models"][0]["formats"] == [{"name": "GGUF", "hf": "a/m1-gguf"}]
    assert notes == []


def test_a_row_with_a_real_format_keeps_it_verbatim():
    """Normalisation never touches a row that already says the right thing."""

    # Given a row with GGUF + MLX
    formats = [{"name": "GGUF", "hf": "p/m-gguf"}, {"name": "MLX", "hf": "p/m-mlx"}]
    store = _store(_row("m", "M", formats))

    # When the store is normalised
    out, notes = sr.normalise(store)

    # Then the entries are unchanged (and so is the rest of the row)
    assert out["models"] == [dict(store["models"][0], formats=formats)]
    assert notes == []


# ---------------------------------------------------------------------------
# rows
# ---------------------------------------------------------------------------
def test_every_distinct_row_is_kept_and_only_a_duplicate_id_is_dropped():
    """Rows are distinct models (a finetune, an MLX conversion, a per-box run): never folded."""

    # Given two rows that look related and one exact duplicate id
    store = _store(
        _row("qwen3.8-27b", "Qwen3.8-27B", [{"name": "GGUF"}]),
        _row("qwen3.8-27b-defiance", "Qwen3.8-27B Defiance Uncensored", [{"name": "GGUF"}]),
        _row("qwen3.8-27b", "Qwen3.8-27B", [{"name": "GGUF"}]),
    )

    # When the store is normalised
    out, notes = sr.normalise(store)

    # Then both distinct models survive and the duplicate is the only drop, named
    assert [m["id"] for m in out["models"]] == ["qwen3.8-27b", "qwen3.8-27b-defiance"]
    assert any("dropped duplicate row 'qwen3.8-27b'" in n for n in notes), notes


# ---------------------------------------------------------------------------
# the sync itself, end to end on a local pair
# ---------------------------------------------------------------------------
def test_sync_writes_the_normalised_store_and_check_accepts_it(tmp_path):
    """`make sync-registry` writes the normalised store; `make check-registry` reads it back."""

    # Given an upstream store (junk formats) and a README whose table is that store's list
    store = _store(_row("m1", "Model One", [{"name": "Model One"}], hf="a/m1-gguf"))
    src = tmp_path / "upstream.json"
    src.write_text(json.dumps(store))
    readme = tmp_path / "README.md"
    readme.write_text("# up\n\n## ❤️ Most loved open-weight models\n\n"
                      "| Model | Status | Trend | CUDA t/s (best) | Metal t/s (best) | CPU t/s (best) | "
                      "ROCm t/s (best) | VRAM | Why people love it |\n|---|---|---|---|---|---|---|---|---|\n"
                      "| [**Model One**](https://huggingface.co/a/m1)<br><sub>x</sub> | t | 1 | "
                      "**10** t/s<br>[llama.cpp](https://github.com/ggml-org/llama.cpp) | — | — | — | "
                      "**16GB**<br><sub>stated</sub> | y |\n")
    dest, readme_dest = tmp_path / "data" / "models.json", tmp_path / "data" / "trending-README.md"

    # When the sync runs against that pair
    rc = sr.sync(str(src), dest, readme_src=str(readme), readme_dest=readme_dest)

    # Then it wrote the normalised row and the shipped file still passes the shape check
    # (the link probe is `make check-registry`'s job and needs the network: not this test)
    assert rc == 0
    written = dest.read_bytes()
    data = sr.validate(written)
    assert data["models"][0]["formats"] == [{"name": "GGUF", "hf": "a/m1-gguf"}]
    assert json.loads(written)["models"][0]["id"] == "m1"
    assert readme_dest.read_text() == readme.read_text()


def test_a_format_written_in_another_spelling_is_still_that_format():
    """Upstream spells the SAME format several ways; identity is the letters and digits,
    not the punctuation (issue #730)."""

    # Given the spellings upstream has used for the vocabulary
    cases = {"LiteRT-LM": "litertlm", "litertlm": "litertlm", "MLX-Safetensors": "mlx-safetensors",
             "mlx-safetensors": "mlx-safetensors", "GGUF": "GGUF", "gguf ": "GGUF"}

    # When  each is canonicalised
    got = {name: sr._canon_format(name) for name in cases}

    # Then  every real format keeps its identity, in the vocabulary's own spelling
    assert got == cases

    # And   what is NOT a format is still dropped (never guessed into one)
    for junk in ("Ornith 1.5", "LLM (MoE)", "", None):
        assert sr._canon_format(junk) is None
