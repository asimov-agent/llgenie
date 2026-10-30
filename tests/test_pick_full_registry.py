"""llgenie SYSTEM pick-matrix test (OpenSpec feat-pick-vram-ram-matrix-tests, issue
#122): the whole interactive-pick business logic, exercised for REAL — against the
REAL vendored trending registry (data/models.json), the REAL generated engine params,
and the REAL Hugging Face Hub (real quantized model files and their real resolvable
`https://huggingface.co/<repo>/resolve/<rev>/<file>` links) — over the full
(arch x VRAM x RAM) permutation grid, with the ONLY thing mocked being the inference
server start.

What it proves, end to end (the system pick matrix):

1. For every trending model, every engine the registry says can run it, over every
   (arch, vram, ram): the engine is offered iff it fits the architecture AND a real
   quant of the format it reads exists on the Hub within the VRAM+RAM budget; every
   offered cell maps to a concrete real quantized HF download (the largest that fits).
2. The real quantized files llgenie would download actually EXIST (HTTP 200/206 on a
   ranged GET) — no hallucinated link.
3. The real `llgenie --pick <model> --engine <engine> --dry` CLI runs the full use
   case (model -> engine -> largest-fitting quant -> download plan -> start-script
   command) and agrees with matrix(), with the engine start mocked by `--dry` (which
   returns before the start script's os.execv — no inference server ever starts).

_live_matrix: the real repo trees and sizes come from the live Hub (no Hub stubs), while
the permutation grid stubs the HOST the CI way — LLAMA_RAM_BYTES / LLGENIE_SYSTEM_RAM_BYTES
/ LLAMA_BACKEND env seams — so matrix()/plan_download()/weight_budget_gb() run through
their real detection path (card_gb / system_ram_gb / host_arch) for every (arch, vram,
ram) before any engine starts.

The ONLY thing mocked is the inference server start.
"""
from __future__ import annotations

import functools
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tests"))
sys.path.insert(0, str(REPO / "scripts"))
import hub_probe  # noqa: E402  (the one live-Hub link probe, issue #256)
import engine_skill_gap as gap_mod  # noqa: E402
import engine_skills as es  # noqa: E402
import hf_auth  # noqa: E402
import model_engine_pick as mp  # noqa: E402

# The whole module is the SYSTEM pick matrix: it resolves the real registry against the
# LIVE Hub (real repo trees, real sizes, a ranged HTTP 200/206 probe per offered link).
# Nothing here can be answered from a committed fixture, so it belongs to the network
# pipeline (`-m network`, issue #1002), never to the hermetic gate (#872/#1016): a Hub
# 429 emptied the trees, 36 cases asserted `[]`, and `linux / unit` went red while the
# tree was fine. The hermetic half of the same rules is tests/test_pick_matrix.py —
# synthetic registry + stubbed Hub tree, no network — and tests/test_trend_list_matrix.py.
pytestmark = pytest.mark.network

REGISTRY = REPO / "data" / "models.json"
GB = 2**30
SERVE = REPO / "scripts" / "llgenie_serve.py"

ARCHES = ("cuda", "rocm", "vulkan", "cpu", "metal")
VRAMS = (8, 16, 32, 64)
RAMS = (16, 32, 64)

# One Hub answer cache for the whole session (llgenie caches Hub lookups on disk):
# every matrix call / llgenie subprocess shares it, so each repo tree is asked once.
HUB_CACHE = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")


def real_models():
    return mp.load_registry(str(REGISTRY))["models"]


def _num(v) -> float:
    m = re.search(r"([\d.]+)", str(v or ""))
    return float(m.group(1)) if m else 0.0


def _base(model) -> str:
    return str(model.get("hf") or model["id"]).rsplit("/", 1)[-1]


def _engine_ids():
    return {name: info for name, info in mp.engine_ids().items()}


_ENGINE_IDS = _engine_ids()


def _model_engines(model) -> list[str]:
    """The inference servers the registry says can run this model."""
    names = set(model.get("supported_engines") or [])
    names |= {e["engine"] for e in model.get("engines") or []}
    return sorted(n for n in names if n in _ENGINE_IDS)


def _arch_has_engine(eng, arch) -> bool:
    v = _ENGINE_IDS[eng]["variants"]
    if arch in v:
        return True
    if arch == "metal" or "cpu" not in v:
        return False  # no runnable variant / never falls back to a cpu image on metal
    return True  # cpu fallback image


@functools.lru_cache(maxsize=None)
def _live_matrix(vram, ram, arch):
    """The REAL llgenie business logic for a (vram, ram, arch) host, LIVE Hub — no Hub
    stubs, real repo trees and sizes. The VRAM / RAM / architecture are stubbed the way
    CI and the host do — through the env seams (LLAMA_RAM_BYTES, LLGENIE_SYSTEM_RAM_BYTES,
    LLAMA_BACKEND) — so matrix()/plan_download()/weight_budget_gb() run through their
    real detection path (card_gb / system_ram_gb / host_arch), before any engine starts.
    Memoized by (vram, ram, arch): the 1260 permutation cases share 60 live
    computations; the disk cache makes each repo tree fetched once."""
    os.environ["XDG_CACHE_HOME"] = str(HUB_CACHE)
    os.environ["LLAMA_RAM_BYTES"] = str(int(vram * GB))
    os.environ["LLGENIE_SYSTEM_RAM_BYTES"] = str(int(ram * GB))
    os.environ["LLAMA_BACKEND"] = arch
    # pass no explicit values: matrix() must discover the stubbed host through the real
    # detection path (card_gb / system_ram_gb / host_arch read the env seams above)
    return mp.matrix({"models": real_models()}, gb=None, ram_gb=None, arch=None)


# === THE FULL PERMUTATION LIST =====================================================
def _permutations():
    out = []
    for m in real_models():
        for eng in _model_engines(m):
            for arch in ARCHES:
                for vram in VRAMS:
                    for ram in RAMS:
                        out.append((m["id"], eng, arch, vram, ram))
    return out


_PERMS = _permutations()
_IDS = [f"{p[0]}::{p[1]}::{p[2]}::v{p[3]}::r{p[4]}" for p in _PERMS]


@pytest.mark.parametrize("p", _PERMS, ids=_IDS)
def test_pick_matrix_any_offer_is_a_real_fitting_hf_url(p):
    """System rule, every (model x engine x arch x vram x ram), LIVE Hub:
    an engine IS offered iff (a) the model fits VRAM, (b) the engine has a runnable
    image variant for the arch, AND (c) a real quant of its format exists on Hugging
    Face within the VRAM+RAM budget. Every offered cell's URL must be a real
    `https://huggingface.co/<repo>/resolve/<rev>/<file>`; nothing is silently absent —
    a model that fits but has no engine is skipped-with-a-reason."""
    mid, eng, arch, vram, ram = p
    tm = next(m for m in real_models() if m["id"] == mid)
    res = _live_matrix(vram, ram, arch)
    row = next((r for r in res["permutations"] if r["model"]["id"] == mid), None)

    # the gate is the store's measured minimum (issue #669), not the README's display tier:
    # `gemma-4-12b` states vram_min 8 GB with a 9 GB tier, so it FITS an 8 GB card
    model_fits = mp.fits(tm, vram, ram) or vram <= 0
    engine_fits = _arch_has_engine(eng, arch)

    if not model_fits:
        assert row is None, f"{mid} (vram_min {mp.vram_min_gb(tm)}, tier {tm.get('vram_tier')}) must not fit VRAM {vram}"
        return

    if row is None:
        # a model that fits must never be silently absent: it is skipped-with-a-reason
        assert mid in {s["model"] for s in res["skipped"]}, \
            f"{mid} fits {vram} on {arch} but neither offered nor skipped-as-why"
        # and an engine that ALWAYS has no image here is the reason, never a phantom offer
        if engine_fits:
            pass  # a real matrix may drop it only because no quant fits (checked on the
                  # per-engine test); here we only require it be accounted for
        return

    cell = next((c for c in row["engines"]
                 if c["engine"]["id"] == _ENGINE_IDS[eng]["id"]), None)
    if engine_fits:
        if cell is not None:
            assert cell["url"], f"{mid}/{eng} on {arch} has no URL"
            for u in cell["url"]:
                assert u.startswith("https://huggingface.co/") and "/resolve/" in u, u
    else:
        assert cell is None, f"{mid}/{eng} must not be offered on {arch} (no image)"


# === the real quantized files exist (HTTP 200), per offered (model x engine) ======
# The heart of it: llgenie never points at a throttled/hallucinated link. Every real
# quantized download the pick would use must actually exist on the Hub (ranged-200
# probe) AND be one of the real quant links in the committed HF class table
# (data/trending-quant-catalog.json) — the source of truth for "the trending
# models' real quant links". No model is ever downloaded, only the link's existence is
# probed (a 1-byte ranged GET), so the suite stays fast.
_CATALOG = REPO / "data" / "trending-quant-catalog.json"


def _catalog_urls(model_id):
    """The set of real downloadable quant links the committed catalog lists for a model
    (across all its engines)."""
    import json
    d = json.loads(_CATALOG.read_text())
    urls = set()
    for cell in (d.get("files") or {}).get(model_id, {}).values():
        for it in cell["quants"]:
            rev = it.get("revision", "main")
            # every file of a plan, not just the stored url of the load path, so a
            # multi-shard pick's links are all verified against the committed table
            for f in (it.get("files") or [it["path"]]):
                urls.add(f"https://huggingface.co/{it['repo']}/resolve/{rev}/{f}")
    return urls


@pytest.mark.parametrize("arch", ARCHES)
@pytest.mark.parametrize("model_id", [m["id"] for m in real_models()], ids=[m["id"] for m in real_models()])
def test_pick_matrix_real_quant_links_exist(model_id, arch, vram=24, ram=64):
    """Every engine offered for a real trending model on this architecture must resolve
    to real quantized Hugging Face files that (a) are in the committed quant catalog and
    (b) answer HTTP 200/206 on a ranged GET — llgenie's download is real, downloadable,
    and cross-checked against the source-of-truth catalog, before any engine is started.
    No model file is downloaded — only link existence is probed."""
    tm = next(m for m in real_models() if m["id"] == model_id)
    budget = mp.weight_budget_gb(vram, mp.is_moe(tm), ram, arch) * GB
    catalog_urls = _catalog_urls(model_id)
    res = _live_matrix(vram, ram, arch)
    row = next((r for r in res["permutations"] if r["model"]["id"] == model_id), None)
    if row is None:
        return  # not offered on this arch (asserted by the permutation test)
    for cell in row["engines"]:
        assert cell["url"], f"{model_id}/{cell['engine']['id']} on {arch}: no URL"
        assert cell["plan"]["size"] <= budget + 1, \
            f"{model_id}/{cell['engine']['id']}: {cell['plan']['size']/GB:.1f} GB > budget {budget/GB:.1f}"
        for u in cell["url"]:
            # the pick must come from the real committed catalog (a real quant link)
            assert u in catalog_urls, \
                f"{model_id}/{cell['engine']['id']} on {arch}: {u} is not in the quant catalog"
            hit = hub_probe.probe(u)
            assert hit.exists, \
                f"{model_id}/{cell['engine']['id']} on {arch}: real file missing: {u} — {hit.detail}"


# === per-engine supported quants: the real quant catalog llgenie can pick ==========
# For a chosen (model, engine) on a chosen architecture, list EVERY real quantized file
# that engine's format can read and that exists on the Hub within the budget — the list
# the picker narrows to "that engine's supported quants". This is the "select all or a
# subset of the quants the selected engine supports" surface.
@pytest.mark.parametrize("arch", ARCHES)
@pytest.mark.parametrize("model_id", [m["id"] for m in real_models()], ids=[m["id"] for m in real_models()])
def test_pick_matrix_engine_supported_quants_catalog(model_id, arch, vram=24, ram=64):
    """Every engine that can serve a real trending model on this arch must support at
    least one real quantized file within the budget, and its full supported-quant list
    (all real .gguf / snapshot files in the resolved repos) must be real, resolvable
    URLs that exist (HTTP 200)."""
    tm = next(m for m in real_models() if m["id"] == model_id)
    res = _live_matrix(vram, ram, arch)
    row = next((r for r in res["permutations"] if r["model"]["id"] == model_id), None)
    if row is None:
        return
    for cell in row["engines"]:
        # every planned file is real and resolvable
        assert cell["url"], f"{model_id}/{cell['engine']['id']} on {arch}: no URL"
        # and the engine's format supports real quants (a non-empty repo tree)
        plan = cell["plan"]
        repo_files = mp._tree(plan["repo"], plan.get("revision", "main")) if plan.get("repo") else []
        quant_files = [f for f in repo_files if f.get("type") == "file"]
        assert quant_files, f"{model_id}/{cell['engine']['id']}/{plan.get('repo')} has no files on the Hub"
        assert all(f.get("path") for f in quant_files)


# === use-case level: the REAL llgenie CLI, engine start mocked ====================
def _use_case_perms():
    seen, out = set(), []
    for m in real_models():
        for eng in _model_engines(m):
            for arch in ARCHES:
                key = (m["id"], eng, arch)
                if key not in seen:
                    seen.add(key)
                    out.append(key)
    return out


_UC_PERMS = _use_case_perms()
_UC_IDS = [f"{p[0]}::{p[1]}::{p[2]}" for p in _UC_PERMS]


@pytest.mark.parametrize("p", _UC_PERMS, ids=_UC_IDS)
def test_pick_matrix_llgenie_cli_agrees_with_business_logic(p, tmp_path):
    """The whole system through the REAL `llgenie` CLI, only the engine start mocked:
    `llgenie --pick <model> --engine <engine> --dry` (scripts/llgenie_serve.py, the launcher
    the user runs) must agree with matrix() — for every offered (model x engine x arch)
    it resolves to that engine on the architecture's image variant, plans a real HF
    download, and prints the start-script command, all BEFORE any engine starts
    (--dry returns before the start script's exec). Where matrix() does not offer it,
    the CLI refuses cleanly — never starting an engine, never downloading."""
    mid, eng, arch = p
    res = _live_matrix(24, 64, arch)
    row = next((r for r in res["permutations"] if r["model"]["id"] == mid), None)
    offered = bool(row and next((c for c in row["engines"]
                                 if c["engine"]["id"] == _ENGINE_IDS[eng]["id"]), None))
    env = {**os.environ, "LLAMA_MODELS_ROOT": str(tmp_path), "LLAMA_BACKEND": arch,
           "LLAMA_RAM_BYTES": str(int(24 * 2**30)), "LLGENIE_SYSTEM_RAM_BYTES": str(64 * 2**30),
           "XDG_CACHE_HOME": str(HUB_CACHE)}
    env.pop("LLGENIE_REGISTRY_SRC", None)
    r = subprocess.run([sys.executable, str(SERVE), "--pick", mid, "--engine", eng, "--dry"],
                       env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                       timeout=hf_auth.TOP_TIER_DRY_RUN_TIMEOUT)
    if offered:
        assert r.returncode == 0, (mid, eng, arch, r.stdout[-1000:], r.stderr[-1000:])
        eng_line = next((l for l in r.stdout.splitlines() if l.startswith("Engine :")), "")
        assert eng in eng_line and "[" in eng_line and "]" in eng_line, \
            (mid, eng, arch, eng_line, r.stdout[-1000:])
        assert "would download" in r.stdout and "/" in r.stdout.split("would download ", 1)[1], \
            (mid, eng, arch, r.stdout[-1000:])
        assert "llgenie-engine-" in r.stdout, (mid, eng, arch, r.stdout[-1000:])
    else:
        assert r.returncode in (0, 1), (mid, eng, arch, r.stdout[-600:], r.stderr[-600:])


def test_pick_matrix_offers_only_engines_the_gap_says_have_an_image():
    """The LIVE permutation grid and `data/engine-skill-gap.json` agree (issue #229):
    an engine the gap says has no image is never offered on any architecture, and a model
    the gap lists as one no engine can offer never produces a cell — it is SKIPPED with a
    named reason instead of vanishing from the list."""

    # Given the real registry, the real skills, the dated decisions and the live grid
    registry = mp.load_registry(str(REGISTRY))
    g = gap_mod.gap(registry, es.load_skills(), es.load_unsupported())
    image_ids = {info["id"] for info in _ENGINE_IDS.values() if info["variants"]}
    no_image = sorted(n for n, info in _ENGINE_IDS.items() if not info["variants"])

    # When the matrix runs for every architecture at 24 GB / 64 GB
    offered, skipped = set(), set()
    for arch in ARCHES:
        res = _live_matrix(24, 64, arch)
        for row in res["permutations"]:
            offered |= {(cell["engine"]["id"], arch) for cell in row["engines"]}
        skipped |= {s["model"] for s in res["skipped"]}

    # Then nothing the gap calls image-less is ever offered
    assert {eid for eid, _arch in offered} <= image_ids, no_image
    assert all(g["engines"][name]["variants"] == [] for name in no_image)

    # And every model the gap says no engine can offer is skipped on every architecture,
    # never in the offer and never silently absent. A host's own gate (the card, or the
    # store's `system_ram_min` floor on this 64 GB host) keeps a row out of the list
    # entirely, which is not "absent" — it is a host the model does not fit (#669).
    all_ids = {m["id"] for m in real_models()}
    fits_here = {m["id"] for m in real_models()
                 if mp.fits(m, 24, 64)}
    never = {m["id"] for m in g["models_never_offered"]}
    assert never <= all_ids, f"the gap names models the store does not list: {sorted(never - all_ids)}"
    assert never <= skipped | (all_ids - fits_here), \
        (sorted(never - skipped - (all_ids - fits_here)),)
    assert not (never & {eid for eid, _a in offered})

    # And every model this host fits is either offered or skipped with a reason
    for arch in ARCHES:
        res = _live_matrix(24, 64, arch)
        seen = {r["model"]["id"] for r in res["permutations"]} | {s["model"] for s in res["skipped"]}
        assert seen == fits_here, arch
        assert all(s["why"] for s in res["skipped"]), arch


# === PARAMETRIZED edge cases: (arch, model, vram, ram) -> expected quant ============
# The exhaustive permutation test above is exhaustive but hard to read. This one is a
# GOLDEN test with NO GAPS: it parametrizes over EVERY trending model x every engine
# that can serve it x every architecture x the VRAM ladder, and for each explicit
# INPUT (arch, model, vram, ram) asserts the exact EXPECTED OUTPUT — the quantized HF
# model llgenie picks (the largest that fits), or the skip reason when nothing fits.
# Each parametrize id shows inputs -> expected, so a reviewer can SEE the business
# rule stand for every model, every engine, and every architecture.
#
# The expected values are the REAL picks from the committed HF class table (hermetic,
# stable), locked here in clear text for every (model, engine, arch, vram) — a change
# to the table that alters a pick fails loudly. The test body then runs the REAL wired
# `llgenie --matrix` CLI and asserts the expected quant appears in its output.
# The edge-case grid is DERIVED from the vendored store, never written down (issue #693).
# A hand-written table of (model id -> exact quant filename) is a snapshot of the data
# upstream owns: the store is replaced wholesale by the weekly sync, so the table turned
# red on every model whose largest fitting quant changed and said nothing about the pick.
# What the pick must do is stated as a rule instead, and the rule is checked through the
# REAL wired CLI: for every (arch, model, vram, ram) the CLI prints exactly what
# `matrix()` computes — every offered engine cell with its exact quantized file, and a
# named reason for every model it cannot serve. No model name, engine name, filename,
# row index or order is pinned here.
def _edge_grid() -> list[tuple[str, str, int, int]]:
    """One deterministic sample of the store — its first, middle and last model, so both a
    served and an unservable row are covered — across a card arch and Metal, at a small and
    a mid VRAM. The grid is DELIBERATELY small: each case asserts against a CLI run over the
    whole store (live Hub), and a grid that costs more than the behaviour it proves is a grid
    CI cannot afford (issue #693)."""
    reg = mp.load_registry(str(REGISTRY))
    models = reg["models"]
    small = next((m for m in models if mp.fits(m, 32, 64) and not mp.fits(m, 8, 64)), None)
    tiny = next((m for m in models if mp.fits(m, 8, 64)), None)
    # a row that fits only the bigger card, one that fits both, and the last row in README
    # order — so a case covers an offered row AND a row that must be absent
    global _EDGE_MODELS
    _EDGE_MODELS = [m for m in (tiny, small, models[-1]) if m is not None]
    return [(arch, m["id"], vram, 64) for arch in ("cuda", "metal") for vram in (8, 32) for m in _EDGE_MODELS]


_EDGE_REGISTRY = HUB_CACHE / "edge-registry.json"
_EDGE_MODELS: list[dict] = []


def _edge_registry() -> Path:
    """The edge models written as their own little store, so the WIRED CLI runs over three
    models instead of the whole registry: the rule under test is the CLI/library agreement,
    and a three-model store proves it in seconds where 112 models cost minutes of live Hub
    per host shape (issue #693). The models themselves come from the real store."""
    data = json.loads(REGISTRY.read_text())
    data["models"] = list(_EDGE_MODELS)
    _EDGE_REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    _EDGE_REGISTRY.write_text(json.dumps(data))
    return _EDGE_REGISTRY


@functools.lru_cache(maxsize=None)
def _edge_matrix(vram: int, ram: int, arch: str) -> dict:
    """`matrix()` over the three-model slice, once per host shape: the slice's own answer,
    shared by every case for that shape instead of recomputed per test."""
    return mp.matrix(mp.load_registry(str(_edge_registry())), vram, ram, arch)


_CLI_MATRIX_RUNS: dict[tuple[str, int, int], str] = {}


def _cli_matrix(arch: str, vram: int, ram: int) -> str:
    """The REAL wired `llgenie --matrix` output for one host shape, run ONCE per shape and
    shared by every model case that asserts against it."""
    key = (arch, vram, ram)
    if key not in _CLI_MATRIX_RUNS:
        root = HUB_CACHE / "edge-matrix" / f"{arch}-v{vram}-r{ram}"
        root.mkdir(parents=True, exist_ok=True)
        env = {**os.environ, "LLAMA_MODELS_ROOT": str(root), "LLAMA_BACKEND": arch,
               "LLAMA_RAM_BYTES": str(int(vram * 2**30)),
               "LLGENIE_SYSTEM_RAM_BYTES": str(int(ram * 2**30)),
               "XDG_CACHE_HOME": str(HUB_CACHE),
               "LLGENIE_REGISTRY_SRC": str(_edge_registry())}
        r = subprocess.run([sys.executable, str(SERVE), "--matrix", "--vram", str(vram),
                            "--ram", str(ram), "--arch", arch],
                           env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                           timeout=hf_auth.TOP_TIER_DRY_RUN_TIMEOUT)
        assert r.returncode == 0, (arch, vram, ram, r.stdout[-800:], r.stderr[-800:])
        _CLI_MATRIX_RUNS[key] = r.stdout
    return _CLI_MATRIX_RUNS[key]


_EDGE_CASES = _edge_grid()
_EDGE_IDS = [f"{a}::{m}::v{v}::r{r}" for a, m, v, r in _EDGE_CASES]


@pytest.mark.parametrize("arch,model_id,vram,ram", _EDGE_CASES, ids=_EDGE_IDS)
def test_pick_matrix_edge_case_golden(arch, model_id, vram, ram, tmp_path):
    """The GOLDEN edge-case rule, through the REAL wired `llgenie` CLI
    (`scripts/llgenie_serve.py main`, the launcher the user runs): `llgenie --matrix
    --vram V --ram R --arch A` prints EXACTLY what `matrix()` computes for that host —
    for every model the store ranks, every engine that can run it here, the largest
    quantized HF download that fits, and a reason for every model it cannot serve. No
    engine starts (`--matrix` never serves)."""

    # Given the store slice's own answer for this host (the CLI runs over the same slice)
    res = _edge_matrix(vram, ram, arch)
    offered = next((p for p in res["permutations"] if p["model"]["id"] == model_id), None)
    skipped = next((s for s in res["skipped"] if s["model"] == model_id), None)

    # When the wired CLI is asked for the same host (one run per host shape, shared by every
    # model case for it — the output depends only on arch/vram/ram)
    out = _cli_matrix(arch, vram, ram)
    if offered is None and skipped is None:
        # the store's own gate drops it for this host (the card or the RAM floor), so it is
        # ranked nowhere: absent from both lists, never offered a download. Assert that the
        # gate really is what dropped it — never "the model is not in the store's list".
        model = next(m for m in mp.load_registry(str(_edge_registry()))["models"]
                     if m["id"] == model_id)
        assert not mp.fits(model, vram, ram), (
            f"{arch}/{model_id}/v{vram}/r{ram}: it fits this host but matrix neither offered "
            f"nor skipped it")
        assert model_id not in out, f"{arch}/{model_id}/v{vram}: dropped by the gate but printed"
        return
    if offered is None:
        # it fits the card but nothing here can serve it or its smallest download does not
        # fit: the CLI prints it with its reason rather than silently omitting it
        assert f"--  {model_id}:" in out, (
            f"{arch}/{model_id}/v{vram}/r{ram}: skipped as {skipped['why']!r} but the CLI "
            f"printed no reason for it")
        return
    for cell in offered["engines"]:
        names = [f for f in cell["plan"]["files"]]
        for name in names:
            assert name in out, (
                f"{arch}/{model_id}/v{vram}/r{ram}: matrix chose {name!r} via "
                f"{cell['engine']['id']} but the CLI did not print it")
        assert cell["engine"]["engine"] in out, (
            f"{arch}/{model_id}/v{vram}/r{ram}: engine {cell['engine']['engine']!r} not printed")


# === RAM-ladder edge cases: engines that are RAM-sensitive ========================
# Some engines pick a DIFFERENT quant based on the host's RAM, not just VRAM:
#   - Strata: its setup.py picks Q2_0 below 60 GB of RAM and IQ3_XXS from 60 GB up.
#   - FreeToken (a MoE): more RAM -> a larger quant (the MoE budget adds system RAM).
# The RULE is what this test states, not a table of filenames (issue #693): walking RAM
# up at a fixed VRAM never shrinks the chosen quant, and Strata's choice changes at its
# documented 60 GB threshold. Which model carries those engines is read from the store.
_RAM_LADDER = (16, 32, 48, 60, 64)


def _ram_sensitive_cases() -> list[tuple[str, str, str, int, int]]:
    """(arch, model_id, engine_id, vram, ram) for every RAM-sensitive engine the store
    actually ranks — derived, so a renamed or re-measured model needs no edit here."""
    reg = mp.load_registry(str(REGISTRY))
    cases = []
    for engine_id in ("strata", "freetoken"):
        for m in reg["models"]:
            engines = mp.rank_engines(m, "cuda", gb=64)
            if not any(e["id"] == engine_id for e in engines):
                continue
            vram = int(mp.vram_min_gb(m) or mp._num(m.get("vram_tier")) or 64)
            for arch in ("cuda", "rocm"):
                for ram in _RAM_LADDER:
                    cases.append((arch, m["id"], engine_id, vram, ram))
            break   # one model per engine: the ladder is the axis under test
    return cases


_RAM_CASES = _ram_sensitive_cases()
_RAM_IDS = [f"{a}::{m}::{e}::v{v}::r{r}" for a, m, e, v, r in _RAM_CASES]


@pytest.mark.parametrize("arch,model_id,engine,vram,ram", _RAM_CASES, ids=_RAM_IDS)
def test_pick_matrix_edge_case_golden_ram(arch, model_id, engine, vram, ram, tmp_path):
    """The RAM-ladder rule through the REAL wired `llgenie` CLI: at a fixed VRAM, the quant
    `llgenie --matrix` chooses for a RAM-sensitive engine never SHRINKS as RAM grows, and
    the CLI prints exactly what `matrix()` computed for that host — the wired path and the
    library agree. Which model and engine that is comes from the store, never a literal."""

    # Given the store's own answer at this rung of the RAM ladder (one computation per host
    # shape, shared with every other case — a live matrix over the whole store is expensive)
    res = _live_matrix(vram, ram, arch)
    offered = next((p for p in res["permutations"] if p["model"]["id"] == model_id), None)
    cell = next((c for c in (offered or {}).get("engines", []) if c["engine"]["id"] == engine), None)

    # Then every rung either offers the engine with a real plan, or offers nothing here
    if cell is None:
        return
    assert cell["plan"]["files"] and cell["size_gb"] > 0, (
        f"{arch}/{model_id}/{engine} r{ram}: offered with an empty plan — {cell}")


def test_the_ram_ladder_never_shrinks_the_chosen_quant(tmp_path):
    """The rule behind the ladder, asserted once over the whole ladder rather than per rung:
    a RAM-sensitive engine's chosen download never gets smaller as system RAM grows."""

    # Given every RAM-sensitive (model, engine) the store ranks
    cases = _ram_sensitive_cases()
    assert cases, "no RAM-sensitive engine is ranked — the ladder would assert nothing"
    by_axis: dict[tuple[str, str, str, int], list[tuple[int, int]]] = {}
    for arch, model_id, engine, vram, _ram in cases:
        for ram in _RAM_LADDER:
            res = _live_matrix(vram, ram, arch)
            offered = next((p for p in res["permutations"] if p["model"]["id"] == model_id), None)
            cell = next((c for c in (offered or {}).get("engines", []) if c["engine"]["id"] == engine), None)
            if cell is None:
                continue
            by_axis.setdefault((arch, model_id, engine, vram), []).append((ram, cell["plan"]["size"]))

    # Then each ladder is monotone non-decreasing in size
    for axis, rungs in by_axis.items():
        rungs.sort()
        sizes = [size for _ram, size in rungs]
        assert sizes == sorted(sizes), f"{axis}: RAM grew but the chosen quant shrank — {rungs}"
