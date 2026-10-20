#!/usr/bin/env python3
"""A Strata family with no Hub URL must not kill the engine bump (issue #416).

Strata's `setup.py` FAMILIES table describes the families its runtime can install. `nvfp4` is a
vendor-hosted / local one: it carries `name`, `tag`, `title`, `by`, `about`, `mmproj`,
`mmproj_sha256` and `ready` — and no `hf`. `scripts/strata_models.py::extract()` used to index
`fam["hf"]` unconditionally, so `make sync-strata-models` raised `KeyError: 'hf'` the moment the
bump moved the pin past that commit, and every Strata bump died (run 39265221145).

These tests run the real loader and the real vendoring function against a fixture `setup.py`, and
the real consumer helpers against a fixture map — no network, no Strata checkout.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import model_engine_pick as MP  # noqa: E402
import strata_models as SM  # noqa: E402

HF_FAMILY = "https://huggingface.co/ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF/resolve/" \
            "ed59f92082b1e93c0e96d60a8b11aab089b52f09/{q}/"

SETUP_PY = f'''
FAMILIES = {{
    "qwen": {{"name": "Qwen", "tag": "qwen", "title": "Qwen3.8-Flash-Next", "by": "ISTA-DASLab",
              "about": "fixture", "hf": "{HF_FAMILY}",
              "file": "Qwen3.8-Flash-Next-GSQ-RCO-{{q}}-0000{{i}}-of-00002.gguf", "shards": 2,
              "mmproj": "mmproj.gguf", "mmproj_hf": "mmproj.gguf"}},
    "nvfp4": {{"name": "NVFP4", "tag": "nvfp4", "title": "NVFP4 (vendor-hosted)", "by": "Niko1221",
               "about": "fixture", "mmproj": "mmproj.gguf", "mmproj_sha256": "deadbeef",
               "ready": True, "file": "nvfp4-{{q}}.gguf", "shards": 1}},
}}

MODELS = {{
    "IQ3_XXS": {{"download_gb": 9.5, "ram_gb": 16, "families": ["qwen"]}},
    "NV1": {{"download_gb": 4.0, "ram_gb": 8, "families": ["nvfp4"]}},
}}

HF_REVISIONS = {{"ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF": "ed59f92082b1e93c0e96d60a8b11aab089b52f09"}}


def main():
    raise SystemExit("setup.py must not run its installer when imported")
'''


def _checkout(tmp_path: Path) -> Path:
    """A minimal Strata checkout: the loader only reads setup.py."""
    (tmp_path / "setup.py").write_text(SETUP_PY)
    return tmp_path


def test_a_family_without_a_hub_url_is_extracted_not_fatal(tmp_path):
    """The exact `KeyError: 'hf'` that reds every Strata bump is gone."""
    # Given a setup.py whose second family is vendor-hosted (no `hf` key at all)
    src = _checkout(tmp_path)

    # When  the map is extracted
    data = SM.extract(src)

    # Then  both families are described, and the Hub-less one says so instead of raising
    assert set(data["families"]) == {"qwen", "nvfp4"}
    assert data["families"]["nvfp4"]["hub"] is False
    assert "repo" not in data["families"]["nvfp4"], "no repo may be invented for it"
    assert data["families"]["nvfp4"]["shards"] == 1


def test_a_family_with_a_hub_url_keeps_todays_shape_and_order(tmp_path):
    """The committed file is compared as TEXT, so the Hub family's key order must not move."""
    # Given the Hub family
    src = _checkout(tmp_path)

    # When  the map is extracted
    qwen = SM.extract(src)["families"]["qwen"]

    # Then  its keys are exactly the committed order, with the URL split into repo/revision/subdir
    assert list(qwen) == ["title", "repo", "revision", "subdir", "file", "shards", "experimental"]
    assert qwen["repo"] == "ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF"
    assert qwen["revision"] == "ed59f92082b1e93c0e96d60a8b11aab089b52f09"
    assert qwen["subdir"] == "{q}/"


def test_the_committed_map_states_no_hub_flag_at_the_current_pin():
    """Byte-stability: at the current pin every family is Hub-hosted, so nothing new is written."""
    # Given the committed data/strata_models.json
    committed = json.loads((ROOT / "data" / "strata_models.json").read_text())

    # When  its families are read
    # Then  none carries the `hub: false` marker (the file is still the pinned setup.py's shape)
    for name, fam in committed["families"].items():
        assert fam.get("hub") is not False, f"{name} unexpectedly marked not-Hub"
        assert fam["repo"], f"{name} is Hub-hosted at this pin"


def test_a_hub_less_family_is_never_mapped_to_a_first_shard(tmp_path, monkeypatch):
    """`strata_first_shards()` walks every family: the Hub-less one must be skipped, not crashed."""
    # Given a vendored map whose first family is Hub-hosted and whose second is not
    data = SM.extract(_checkout(tmp_path))
    fixture = tmp_path / "strata_models.json"
    fixture.write_text(json.dumps(data))
    monkeypatch.setattr(MP, "STRATA_MODELS", fixture)

    # When  the first-shard map is built
    shards = MP.strata_first_shards()

    # Then  only the Hub family contributes, and nothing raised
    assert shards, "the Hub family still maps its first shard"
    assert all(fam == "qwen" for fam, _ in shards.values())


def test_a_hub_less_family_cannot_be_asked_for_its_files(tmp_path, monkeypatch):
    """A caller asking for a Hub-less family's shards is told, not given a path built from None."""
    # Given the same vendored map
    data = SM.extract(_checkout(tmp_path))
    fixture = tmp_path / "strata_models.json"
    fixture.write_text(json.dumps(data))
    monkeypatch.setattr(MP, "STRATA_MODELS", fixture)

    # When  its files are requested
    # Then  it raises a named error instead of a KeyError on `repo`
    try:
        MP.strata_files("nvfp4", "NV1")
    except ValueError as exc:
        assert "not Hub-downloadable" in str(exc)
    else:
        raise AssertionError("strata_files must refuse a family with no repo")
