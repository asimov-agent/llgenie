#!/usr/bin/env python3
"""A Strata family with no Hub URL is a shape, not a snapshot (#416, and the test that red #605).

Strata's `setup.py` FAMILIES table describes the families its runtime can install. `nvfp4` is a
vendor-hosted / local one: it carries `name`, `tag`, `title`, `by`, `about`, `mmproj`,
`mmproj_sha256` and `ready` — and no `hf`. `scripts/strata_models.py::extract()` used to index
`fam["hf"]` unconditionally, so `make sync-strata-models` raised `KeyError: 'hf'` the moment the
bump moved the pin past that commit, and every Strata bump died (run 39265221145).

The OTHER half of that bug was a test asserting the file's literal contents at pin v0.1.43 ("every
family is Hub-hosted"), so the first CORRECT bump that surfaced `nvfp4` (v0.2.6, #605) went red on
`nvfp4 unexpectedly marked not-Hub` — the bump did nothing wrong, the test described the previous
pin. What is locked here is the invariant instead: a family is Hub-hosted (`repo` + `revision` +
`subdir`, no `hub` key) or explicitly not-Hub (`hub: false`, no repo), never both, never neither,
whatever set of families the pin declares; the not-Hub set is derived from the `setup.py` being
extracted, never from a list in this file. Whether the committed map still matches the PINNED
`setup.py` is `make check-strata-models`' byte comparison (`tests/test_strata_download.py` asserts
the derived set against the fetched pin).

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


def _checkout_with(tmp_path: Path, families: dict) -> Path:
    """A checkout whose `FAMILIES` table is the one handed in, so the expectation can be derived."""
    models = {name: {"download_gb": 4.0, "ram_gb": 8, "families": [name]} for name in families}
    (tmp_path / "setup.py").write_text(
        f"FAMILIES = {families!r}\n\nMODELS = {models!r}\n\nHF_REVISIONS = {{}}\n\n\n"
        "def main():\n    raise SystemExit('setup.py must not run its installer when imported')\n")
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


HUB_SHAPE = {
    "title": "Qwen3.8-Flash-Next", "repo": "ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF",
    "revision": "ed59f92082b1e93c0e96d60a8b11aab089b52f09", "subdir": "{q}/",
    "file": "Qwen3.8-Flash-Next-GSQ-RCO-{q}-0000{i}-of-00002.gguf", "shards": 2,
    "experimental": False,
}
NOT_HUB_SHAPE = {
    "title": "NVFP4 (vendor-hosted)", "hub": False, "file": "nvfp4-{q}.gguf", "shards": 1,
    "experimental": False,
}


def test_the_committed_map_is_hub_hosted_or_explicitly_not_at_whatever_the_pin_is():
    """The invariant, not a snapshot: v0.1.43 has no not-Hub family, v0.2.6 has exactly `nvfp4`.

    A test that instead asserts "nothing is not-Hub" describes the pin it was written at and reds
    the next correct bump (#605: v0.2.6's `nvfp4` has no `hf`, so `hub: false` is the right answer).
    """
    # Given the committed data/strata_models.json
    committed = json.loads((ROOT / "data" / "strata_models.json").read_text())

    # When  its family table is checked against the shape rule
    problems = SM.family_shape_problems(committed["families"])

    # Then  every family is exactly one of the two shapes — whichever ones the pin decides
    assert problems == []

    # And   the map is the PINNED setup.py's copy, so a stale map cannot pass as the invariant
    url, _ref, sha = SM.pinned()
    assert committed["pinned"] == sha
    assert committed["source"] == f"{url}/blob/{sha}/setup.py"


def test_the_shape_rule_holds_at_both_pins_that_matter():
    """v0.1.43 (all Hub) and v0.2.6 (`nvfp4` added, vendor-hosted) both satisfy the same rule."""
    root = {**HUB_SHAPE, "subdir": ""}  # `swift` at v0.1.43 is published at the repo root
    for label, families in (
        ("v0.1.43 — every family Hub-hosted", {"qwen": HUB_SHAPE, "swift": root}),
        ("v0.2.6 — nvfp4 is vendor-hosted", {"qwen": HUB_SHAPE, "nvfp4": NOT_HUB_SHAPE}),
    ):
        # Given a family table in that pin's shape, When it is checked, Then nothing is wrong
        assert SM.family_shape_problems(families) == [], label


def test_the_shape_rule_names_the_defect_it_exists_for():
    """A family that is both, neither, or wrongly marked is reported by name, never accepted."""
    cases = {
        "a not-Hub family that still carries a repo": ({**HUB_SHAPE, "hub": False},
                                                       "marked not-Hub (`hub: false`) but carries a repo"),
        "a not-Hub family with a revision to build a URL from": ({**NOT_HUB_SHAPE, "revision": "x" * 40},
                                                                 "carries `revision`"),
        "a family with neither a repo nor the marker": ({"title": "X", "file": "x.gguf", "shards": 1},
                                                        "neither a repo nor `hub: false`"),
        "a Hub family carrying `hub: true`": ({**HUB_SHAPE, "hub": True},
                                              "carries a `hub` key but is Hub-hosted"),
        "a Hub family with no revision": ({k: v for k, v in HUB_SHAPE.items() if k != "revision"},
                                          "Hub-hosted but no `revision`"),
    }
    for label, (family, expected) in cases.items():
        # Given a map whose single family has that defect, Then the defect is named
        problems = SM.family_shape_problems({"fam": family})
        assert problems, label
        assert expected in problems[0], f"{label}: {problems}"


def test_the_not_hub_set_is_derived_from_the_setup_py_never_from_a_list(tmp_path):
    """The expectation is read from the setup.py being extracted, so it survives the next bump."""
    # Given a setup.py with two Hub families and two with no `hf` at all
    families = {
        "qwen": {"name": "Qwen", "title": "Qwen3.8-Flash-Next", "hf": HF_FAMILY,
                 "file": "q-{q}-0000{i}.gguf", "shards": 2},
        "swift": {"name": "Swift", "title": "Swift", "hf": HF_FAMILY,
                  "file": "s-{q}-0000{i}.gguf", "shards": 1},
        "nvfp4": {"name": "NVFP4", "title": "NVFP4", "file": "nvfp4-{q}.gguf", "shards": 1},
        "vendor": {"name": "Vendor", "title": "Vendor", "file": "v-{q}.gguf", "shards": 1},
    }
    src = _checkout_with(tmp_path, families)

    # When  the map is extracted
    data = SM.extract(src)

    # Then  the not-Hub set is exactly the families this setup.py declares without an `hf`
    want = {name for name, fam in families.items() if "hf" not in fam}
    assert want, "the fixture must carry a not-Hub family or it proves nothing"
    assert {n for n, f in data["families"].items() if f.get("hub") is False} == want

    # And   the extracted table satisfies the shape rule itself
    assert SM.family_shape_problems(data["families"]) == []


def test_check_names_a_malformed_map_instead_of_only_a_diff(tmp_path, capsys):
    """`make check-strata-models` says WHAT is wrong, not just that 100 lines differ."""
    # Given a map whose only family is marked not-Hub AND still carries its Hub repo
    src = _checkout_with(tmp_path, {"qwen": {"name": "Qwen", "title": "Qwen", "hf": HF_FAMILY,
                                             "file": "q-{q}-0000{i}.gguf", "shards": 2}})
    bad = SM.extract(src)
    bad["families"]["qwen"]["hub"] = False
    out = tmp_path / "m.json"
    out.write_text(json.dumps(bad, indent=2) + "\n")

    # When  check runs against it
    rc = SM.main(["check", "--src", str(src), "--out", str(out)])

    # Then  it fails and names the family and the defect
    assert rc == 1
    err = capsys.readouterr().err
    assert "qwen: marked not-Hub (`hub: false`) but carries a repo" in err


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
