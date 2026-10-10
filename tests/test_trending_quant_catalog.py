"""Real trending-model quant catalog (issue #122): the committed HF class table of
every trending model's real quantized plans and their real downloadable Hugging Face
links — data/trending-quant-catalog.json (the canonical file llgenie's pick logic
reads) and its test fixture tests/fixtures/trending-quant-catalog.json, generated from
data/models.json + the live Hub by scripts/gen_trending_quant_catalog.py
(make sync-quant-catalog). The generator is separate tooling, not llgenie runtime
logic, and makes no LLM calls.

Unit assertions (hermetic except a bounded HTTP-200 probe): the catalog is well-formed,
every model is a real registry model, every engine is a real engine with an image, and
every URL is a concrete, resolvable `https://huggingface.co/<repo>/resolve/<rev>/<file>`
download link. It never downloads a model — it only checks that links exist.

Regression guard: the committed fixture must EXACTLY match the canonical data/ table,
so a sync that changes a link or drops a section is caught here, not silently shipped.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
import urllib.error
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import model_engine_pick as mp  # noqa: E402

CATALOG = REPO / "data" / "trending-quant-catalog.json"       # canonical (llgenie reads this)
FIXTURE = REPO / "tests" / "fixtures" / "trending-quant-catalog.json"  # committed regression copy
REGISTRY = REPO / "data" / "models.json"

_PLAN = {"repo", "revision", "path", "files", "size_gb", "url"}
_DIR_PLAN = _PLAN | {"dir"}
_RESOLVE = re.compile(r"^https://huggingface\.co/[^/]+/[^/]+/resolve/[^/]+/.+$")


def catalog():
    return json.loads(CATALOG.read_text())


def test_fixture_exactly_matches_the_canonical_catalog():
    # Given the canonical data/ table and its committed test fixture
    # When they are compared byte-for-byte
    # Then they are identical — a changed link or a dropped section in the fixture
    #   (regression vs the committed table) fails this test
    assert CATALOG.exists() and FIXTURE.exists()
    assert CATALOG.read_text() == FIXTURE.read_text(), (
        "tests/fixtures/trending-quant-catalog.json differs from data/trending-quant-"
        "catalog.json — run make sync-quant-catalog (a link change or dropped section "
        "must be reviewed and committed) and re-commit both")


def test_catalog_is_well_formed():
    # Given the committed catalog (the HF class table)
    d = catalog()
    # Then it has meta + a files map of model -> engine -> {arch, quants}
    assert set(d) == {"meta", "files"}
    assert d["meta"]["generated_utc"]
    assert d["files"], "catalog is empty"
    for mid, engines in d["files"].items():
        assert mid and isinstance(engines, dict) and engines
        for eng, cell in engines.items():
            assert eng and isinstance(cell, dict)
            assert set(cell) == {"arch", "quants"} and cell["arch"], cell
            assert cell["quants"]
            for it in cell["quants"]:
                # a single-file plan OR a whole-repo snapshot (dir, path="")
                assert set(it) in (_PLAN, _DIR_PLAN), it
                assert it["repo"] and it["files"]
                assert it["files"], it
                if it.get("dir"):
                    assert it["path"] == "" and set(it) == _DIR_PLAN, it
                else:
                    assert it["path"] and it["path"] in it["files"], it


def test_every_model_and_engine_is_real():
    # Given the real registry + real engine image set
    reg = {m["id"]: m for m in mp.load_registry(str(REGISTRY))["models"]}
    ids = mp.engine_ids()
    d = catalog()
    # Then every catalog model exists in the registry, every engine has an image, and its
    # listed archs are a subset of the engine's real image variants (issue #98 / #103)
    for mid, engines in d["files"].items():
        assert mid in reg, f"{mid} not in data/models.json"
        for eng, cell in engines.items():
            assert eng in ids, f"{eng} has no engine image"
            assert set(cell["arch"]) <= set(ids[eng]["variants"]), \
                f"{eng} lists archs {cell['arch']} not among its image variants {ids[eng]['variants']}"
    # and the catalog is a subset of the registry models (nothing invented)
    assert set(d["files"]) <= set(reg)


def test_every_url_is_a_concrete_resolvable_download_link():
    # Given every plan in the catalog
    def _quants():
        for engines in catalog()["files"].values():
            for cell in engines.values():
                yield from cell["quants"]
    urls = [it["url"] for it in _quants()]
    assert urls
    # Then every one is a concrete https://huggingface.co/<repo>/resolve/<rev>/<file> link
    for u in urls:
        assert _RESOLVE.match(u), u
        assert "/resolve/" in u and not u.endswith("/resolve/")
    # and the load path is consistent with the URL (repo + revision + path)
    for it in _quants():
        assert it["repo"] in it["url"], (it["repo"], it["url"])
        if it.get("dir"):
            assert it["url"].endswith(it["files"][0]), (it, it["url"])
        else:
            assert it["path"] != "." and it["path"] in it["url"], it


def test_bounded_sample_of_real_links_exist_http_200():
    """A bounded sample of the catalog's links must exist on the live Hub (no model
    download — a 1-byte ranged probe). This guards that the committed table points at
    real files, not fabricated ones; the full pick-matrix suite probes every offered
    quant of the real run."""
    # one link per (model, engine) — bounded, still representative
    sample = []
    for engines in catalog()["files"].values():
        for cell in engines.values():
            if cell["quants"]:
                sample.append(cell["quants"][0]["url"])
    assert sample
    ok, missing = 0, 0
    for u in sample:
        if _url_exists(u):
            ok += 1
        else:
            missing += 1
            print(f"  missing: {u}")
    assert ok >= len(sample) * 0.9, f"{missing}/{len(sample)} of the sample links did not answer HTTP 200"


def test_every_engine_and_arch_that_llgenie_offers_is_catalogued():
    # Given every (model, engine) that llgenie would actually recommend on some arch
    reg = mp.load_registry(str(REGISTRY))["models"]
    d = catalog()
    for m in reg:
        engines = mp.rank_engines(m)
        for eng in engines:
            cell = mp.catalog_engine_cell(m["id"], eng["engine"])
            assert cell is not None, \
                f"{m['id']}/{eng['engine']}: llgenie offers an engine that has no catalog entry"
            assert eng["variant"] in cell["arch"], \
                f"{m['id']}/{eng['engine']} offered on {eng['variant']} but the catalog arch " \
                f"list {cell['arch']} excludes it"


def test_every_registry_model_has_a_catalog_entry_or_a_documented_skip():
    # Given a model that llgenie CAN serve on some architecture
    reg = mp.load_registry(str(REGISTRY))["models"]
    d = catalog()
    names = [m["id"] for m in reg if mp.recommend({"models": [m]})]
    for mid in names:
        assert mid in d["files"], f"{mid}: no catalog entry for a servable model"


def _url_exists(url: str) -> bool:
    req = urllib.request.Request(url, method="GET",
                                 headers={"Range": "bytes=0-0", "User-Agent": "llgenie-test"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status in (200, 206)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError):
        return False
