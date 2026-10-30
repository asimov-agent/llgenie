"""Real trending-model quant catalog (issue #122): the committed HF class table of
every trending model's real quantized plans and their real downloadable Hugging Face
links — data/trending-quant-catalog.json (the canonical file llgenie's pick logic
reads) and its test fixture tests/fixtures/trending-quant-catalog.json, generated from
data/models.json + the live Hub by scripts/gen_trending_quant_catalog.py
(make sync-quant-catalog). The generator is separate tooling, not llgenie runtime
logic, and makes no LLM calls.

Unit assertions (hermetic): the catalog is well-formed, every model is a real registry
model, every engine is a real engine with an image, and every URL is a concrete,
resolvable `https://huggingface.co/<repo>/resolve/<rev>/<file>` download link. It never
downloads a model — it only checks that links exist. The live half — the bounded HTTP-200
link probe and the two `offer()` rules that resolve the Hub for anything the table does
not cover — carries `@pytest.mark.network` (#872), so `linux / unit` never waits on the
Hub; `make test-unit-network` (issue #1002) owns them.

Regression guard: the committed fixture must EXACTLY match the canonical data/ table,
so a sync that changes a link or drops a section is caught here, not silently shipped.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tests"))
sys.path.insert(0, str(REPO / "scripts"))
import hub_probe  # noqa: E402  (the one live-Hub link probe, issue #256)
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


@pytest.mark.network
def test_bounded_sample_of_real_links_exist_http_200():
    """A bounded sample of the catalog's links must exist on the live Hub (no model
    download — a 1-byte ranged probe). This guards that the committed table points at
    real files, not fabricated ones; the full pick-matrix suite probes every offered
    quant of the real run.

    It opens one real Hub URL per (model, engine) — 271 of them on the 2026-10-30 table —
    so it runs in the network pipeline (`make test-unit-network`, issue #1002) beside the
    bounded liveness gate, never in `linux / unit` (#872)."""
    # one link per (model, engine) — bounded, still representative
    sample = []
    for engines in catalog()["files"].values():
        for cell in engines.values():
            if cell["quants"]:
                sample.append(cell["quants"][0]["url"])
    assert sample
    ok, missing = 0, 0
    for u in sample:
        hit = hub_probe.probe(u)
        if hit.exists:
            ok += 1
        else:
            missing += 1
            print(f"  missing: {u} — {hit.detail}")
    assert ok >= len(sample) * 0.9, f"{missing}/{len(sample)} of the sample links did not answer HTTP 200"


def _offered_rows(arch: str = "cuda") -> list[dict]:
    """Every row plain `llgenie` prints for a host that fits the whole store.

    `offer()` — not the raw rank list — is the path that decides what a user can pick: it drops an
    engine it cannot fetch and keeps the row with a `why` when nothing is left. So it is where
    "a model llgenie serves is one the table covers" is either true or not, and it is the surface
    these two rules are stated on (issue #750: the raw `rank_engines` list is a step ahead of what
    can actually be downloaded, which is #731's own work item).
    """
    reg = mp.load_registry(str(REGISTRY))
    return mp.offer(reg, arch=arch, gb=1024, ram_gb=1024)


@pytest.mark.network
def test_every_engine_and_arch_that_llgenie_offers_is_catalogued():
    """`offer()` resolves the LIVE Hub for any (model, engine) the committed table does
    not cover, which is what gives this rule its teeth: only a real Hub answer can show
    that llgenie offers something the catalog is missing. It therefore belongs to the
    network pipeline, not the hermetic gate (#872/#1016) — a Hub 429 there starved the
    trees, offered nothing, and red-ed `linux / unit` while the tree was fine."""
    # Given every (model, engine) that llgenie actually offers on a host that fits the store
    d = catalog()
    rows = _offered_rows()

    # When each offered cell is looked up in the committed table
    for row in rows:
        for eng in row["engines"]:
            cell = (d["files"].get(row["model"]["id"]) or {}).get(eng["engine"])

            # Then it has a table cell, and that cell lists the arch it is offered on
            assert cell is not None, \
                f"{row['model']['id']}/{eng['engine']}: llgenie offers an engine that has no catalog entry"
            assert eng["variant"] in cell["arch"], \
                f"{row['model']['id']}/{eng['engine']} offered on {eng['variant']} but the catalog arch " \
                f"list {cell['arch']} excludes it"


@pytest.mark.network
def test_every_registry_model_has_a_catalog_entry_or_a_documented_skip():
    """The same live `offer()` surface as the rule above (see its docstring): a model the
    table omits is only known to be servable because the Hub answered, so this runs in
    the network pipeline rather than the hermetic gate (#872/#1016)."""
    # Given every row plain llgenie prints for a host that fits the whole store
    d = catalog()
    rows = _offered_rows()

    # When each row is asked what it offers
    for row in rows:
        mid = row["model"]["id"]
        if row["engines"]:
            # Then a served model has a table entry ...
            assert mid in d["files"], f"{mid}: no catalog entry for a servable model"
        else:
            # ... and a model nothing here can serve is explained, never silently blank
            assert row["why"], f"{mid}: not offered and no reason given"



# --------------------------------------------- what the generator may plan a cell from (#750)
# Measured on the 2026-10-27 store: the table carried a `safetensors` plan taken from an
# MLX-converted repo (`qwen3-4b` served by vLLM) and an `mlx-safetensors` plan taken from the
# BASE repo (`google/gemma-3-1b-it`, which answers 401), while `plan_download()` — the code
# that actually resolves a download — refuses both. The generator now applies that same rule.
def test_a_safetensors_cell_is_planned_only_from_a_non_mlx_repo(monkeypatch):
    """`safetensors` and `mlx-safetensors` are told apart by the repo's NAME, as plan_download does."""

    # Given a store row whose only format repo is an MLX conversion
    m = {"id": "m1", "hf": "org/m1", "formats": [{"name": "MLX", "hf": "org/m1-mlx-4bit"}]}
    monkeypatch.setattr(mp, "mlx_repos", lambda _m: ["org/m1-MLX-8bit"])

    # When  the repos each format may be planned from are computed
    safe = gen._repos_for(m, "safetensors")
    mlx = gen._repos_for(m, "mlx-safetensors")

    # Then  an MLX-named repo is never a `safetensors` plan, and never the other way round
    assert safe == []
    assert mlx == ["org/m1-mlx-4bit", "org/m1-MLX-8bit"]


def test_a_strata_cell_exists_only_for_the_family_strata_serves(monkeypatch):
    """Strata installs one family's checkpoints, so it has no plan for any other model."""

    # Given a model Strata was MEASURED on and a real-looking Strata plan
    plan = {"repo": "ISTA-DASLab/some-pack", "revision": "abc", "path": "Q2_0/shard-1.gguf",
            "files": ["Q2_0/shard-1.gguf"], "size": 4 * 2**30}
    model = {"id": "not-the-family", "hf": "org/not-the-family",
             "formats": [{"name": "GGUF", "hf": "org/not-the-family-GGUF"}],
             "supported_engines": ["Strata"]}
    monkeypatch.setattr(mp, "strata_plan", lambda _ram=None: plan)

    # When  the cell is generated for a model Strata does NOT serve, then for one it does
    monkeypatch.setattr(mp, "strata_serves", lambda _m: False)
    not_served = gen._model_catalog(model)

    # Then  no cell is invented ...
    assert "Strata" not in not_served
    # ... and the same model served by Strata does get its own plan
    monkeypatch.setattr(mp, "strata_serves", lambda _m: True)
    served = gen._model_catalog(model)
    assert served["Strata"]["quants"][0]["repo"] == "ISTA-DASLab/some-pack"


# ----------------------------------------------------------- the drift guard (`--check`)
# `make check-quant-catalog` regenerates from the LIVE Hub: `mlx_repos()`/`tensorfold_repos()`
# SEARCH huggingface.co, so upstream publishing a new conversion makes a fresh generation
# larger than the committed table with no llgenie change at all. Measured 2026-10-27: four new
# MLX repos turned the gate red on `main` itself, blocking every PR for a reason no PR caused.
# The rule under test is `compare()`'s: a row the committed table HAS must regenerate
# identically (failure), a row the Hub ADDS is a note the next sync records.
import gen_trending_quant_catalog as gen  # noqa: E402

_PLAN_ONE = {"repo": "org/m1-gguf", "revision": "main", "path": "m1-Q4.gguf",
             "files": ["m1-Q4.gguf"], "size_gb": 4.0,
             "url": "https://huggingface.co/org/m1-gguf/resolve/main/m1-Q4.gguf"}
_NEW_PLAN = {"repo": "org/m1-gguf-MLX-4bit", "revision": "main", "path": "",
             "files": ["config.json", "model.safetensors"], "size_gb": 2.0, "dir": True,
             "url": "https://huggingface.co/org/m1-gguf-MLX-4bit/resolve/main/config.json"}


def _committed() -> dict:
    return {"meta": {"generated_utc": "2026-10-13T14:31:40Z"},
            "files": {"m1": {"llama.cpp": {"arch": ["cuda", "cpu"],
                                           "quants": [dict(_PLAN_ONE)]}}}}


def test_an_unchanged_regeneration_is_clean():
    # Given a committed table and the same table regenerated

    # When  the two are compared
    failures, notes = gen.compare(_committed(), json.loads(json.dumps(_committed())))

    # Then  nothing fails and nothing is noted
    assert failures == [] and notes == []


def test_a_repo_upstream_publishes_since_the_sync_is_a_note_not_a_failure():
    # Given a fresh generation that also holds a plan the committed table does not
    fresh = json.loads(json.dumps(_committed()))
    fresh["files"]["m1"]["MLX"] = {"arch": ["metal", "cuda"], "quants": [dict(_NEW_PLAN)]}

    # When  it is compared with the committed table
    failures, notes = gen.compare(_committed(), fresh)

    # Then  the addition is reported and never fails the gate
    assert failures == [], failures
    assert any("MLX" in n for n in notes), notes


def test_a_lost_plan_whose_link_is_dead_still_fails():
    # Given a fresh generation that lost the plan the committed table records, and the
    #   plan's own link answers 404/410 — nothing serves that download any more (#769)
    fresh = json.loads(json.dumps(_committed()))
    fresh["files"]["m1"]["llama.cpp"]["quants"] = []

    # When  it is compared with the committed table
    failures, _notes = gen.compare(_committed(), fresh, probe=lambda u: gen.PROBE_DEAD)

    # Then  the missing plan fails, naming the plan and why it may be dropped
    assert any("404/410" in f for f in failures), failures


def test_a_lost_plan_the_repo_still_serves_is_a_note_not_a_failure():
    # Given the same lost plan, but its repo still answers 200 (it fell off the search page)
    fresh = json.loads(json.dumps(_committed()))
    fresh["files"]["m1"]["llama.cpp"]["quants"] = []

    # When  it is compared with the committed table
    failures, notes = gen.compare(_committed(), fresh, probe=lambda u: gen.PROBE_OK)

    # Then  nothing fails: search churn must not red the one gate every PR runs (#769)
    assert failures == [], failures
    assert any("still reachable (ok)" in n for n in notes), notes


def test_a_changed_plan_is_reported_on_both_sides_and_never_fails():
    # Given a fresh generation whose plan points at a different file — the old URL still
    #   answers, so the download llgenie records has not broken; the search simply
    #   describes it differently now (#769)
    fresh = json.loads(json.dumps(_committed()))
    fresh["files"]["m1"]["llama.cpp"]["quants"][0]["path"] = "m1-Q8.gguf"
    fresh["files"]["m1"]["llama.cpp"]["quants"][0]["url"] = \
        "https://huggingface.co/org/m1-gguf/resolve/main/m1-Q8.gguf"

    # When  it is compared with the committed table
    failures, notes = gen.compare(_committed(), fresh, probe=lambda u: gen.PROBE_OK)

    # Then  both directions are reported for the next sync, and the gate stays green
    assert failures == [], failures
    assert any("still reachable (ok)" in n for n in notes), notes
    assert any("does not record yet" in n for n in notes), notes


def test_a_changed_plan_whose_old_link_is_dead_fails():
    # Given the same changed plan, but the committed URL answers 404/410
    fresh = json.loads(json.dumps(_committed()))
    fresh["files"]["m1"]["llama.cpp"]["quants"][0]["path"] = "m1-Q8.gguf"
    fresh["files"]["m1"]["llama.cpp"]["quants"][0]["url"] = \
        "https://huggingface.co/org/m1-gguf/resolve/main/m1-Q8.gguf"

    # When  it is compared with the committed table
    failures, _notes = gen.compare(_committed(), fresh, probe=lambda u: gen.PROBE_DEAD)

    # Then  the dead plan fails the gate
    assert any("404/410" in f for f in failures), failures


def test_a_catalog_rendered_for_another_registry_still_fails():
    # Given a fresh generation under a newer registry
    fresh = json.loads(json.dumps(_committed()))
    fresh["meta"]["generated_utc"] = "2026-10-27T00:00:00Z"

    # When  it is compared with the committed table
    failures, _notes = gen.compare(_committed(), fresh)

    # Then  the registry the catalog was rendered for is asserted
    assert any("make sync-quant-catalog" in f for f in failures), failures


def test_a_reordered_regeneration_is_a_note_not_a_failure():
    # Given a committed table with two plans, regenerated as the SAME two in another order
    # (`mlx_repos()` ranks the Hub search by downloads, and those move)
    second = {"repo": "org/m1-gguf-MLX-8bit", "revision": "main", "path": "",
              "files": ["config.json", "model.safetensors"], "size_gb": 8.0, "dir": True,
              "url": "https://huggingface.co/org/m1-gguf-MLX-8bit/resolve/main/config.json"}
    committed = _committed()
    committed["files"]["m1"]["llama.cpp"]["quants"] = [dict(_PLAN_ONE), dict(second)]
    fresh = json.loads(json.dumps(committed))
    fresh["files"]["m1"]["llama.cpp"]["quants"] = [dict(second), dict(_PLAN_ONE)]

    # When  it is compared with the committed table
    failures, notes = gen.compare(committed, fresh)

    # Then  the reorder is reported rather than failing the gate on data upstream owns
    assert failures == [], failures
    assert any("different order" in n for n in notes), notes
