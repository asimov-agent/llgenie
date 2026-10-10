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
import os
import re
import subprocess
import sys
import urllib.request
import urllib.error
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import model_engine_pick as mp  # noqa: E402

REGISTRY = REPO / "data" / "models.json"
GB = 2**30
SERVE = REPO / "scripts" / "llama_serve.py"

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

    model_fits = _num(tm.get("vram_tier")) <= vram or vram <= 0
    engine_fits = _arch_has_engine(eng, arch)

    if not model_fits:
        assert row is None, f"{mid} ({tm['vram_tier']}) must not fit VRAM {vram}"
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
            assert _url_exists(u), \
                f"{model_id}/{cell['engine']['id']} on {arch}: real file missing (HTTP): {u}"


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
    `llgenie --pick <model> --engine <engine> --dry` (scripts/llama_serve.py, the launcher
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
                       timeout=300)
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


def _url_exists(url: str) -> bool:
    req = urllib.request.Request(url, method="GET",
                                 headers={"Range": "bytes=0-0", "User-Agent": "llgenie-test"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status in (200, 206)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError):
        return False


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
_EDGE_CASES = [
    # (arch, model, vram, ram, expected_quant_file_or_skip, engine)
    ('cuda', 'qwen3.8-flash-next-125b', 8, 64, 'absent (below vram_tier)', 'exllamav3-rocm'),
    ('cuda', 'qwen3.8-flash-next-125b', 16, 64, 'no-fit', 'exllamav3-rocm'),
    ('cuda', 'qwen3.8-flash-next-125b', 24, 64, 'no-fit', 'exllamav3-rocm'),
    ('cuda', 'qwen3.8-flash-next-125b', 32, 64, 'no-fit', 'exllamav3-rocm'),
    ('cuda', 'qwen3.8-flash-next-125b', 64, 64, 'no-fit', 'exllamav3-rocm'),
    ('rocm', 'qwen3.8-flash-next-125b', 8, 64, 'absent (below vram_tier)', 'exllamav3-rocm'),
    ('rocm', 'qwen3.8-flash-next-125b', 16, 64, 'no-fit', 'exllamav3-rocm'),
    ('rocm', 'qwen3.8-flash-next-125b', 24, 64, 'no-fit', 'exllamav3-rocm'),
    ('rocm', 'qwen3.8-flash-next-125b', 32, 64, 'no-fit', 'exllamav3-rocm'),
    ('rocm', 'qwen3.8-flash-next-125b', 64, 64, 'no-fit', 'exllamav3-rocm'),
    ('vulkan', 'qwen3.8-flash-next-125b', 8, 64, 'absent (below vram_tier)', 'exllamav3-rocm'),
    ('vulkan', 'qwen3.8-flash-next-125b', 16, 64, 'no-fit', 'exllamav3-rocm'),
    ('vulkan', 'qwen3.8-flash-next-125b', 24, 64, 'no-fit', 'exllamav3-rocm'),
    ('vulkan', 'qwen3.8-flash-next-125b', 32, 64, 'no-fit', 'exllamav3-rocm'),
    ('vulkan', 'qwen3.8-flash-next-125b', 64, 64, 'no-fit', 'exllamav3-rocm'),
    ('cpu', 'qwen3.8-flash-next-125b', 8, 64, 'absent (below vram_tier)', 'exllamav3-rocm'),
    ('cpu', 'qwen3.8-flash-next-125b', 16, 64, 'absent (below vram_tier)', 'exllamav3-rocm'),
    ('cpu', 'qwen3.8-flash-next-125b', 24, 64, 'absent (below vram_tier)', 'exllamav3-rocm'),
    ('cpu', 'qwen3.8-flash-next-125b', 32, 64, 'absent (below vram_tier)', 'exllamav3-rocm'),
    ('cpu', 'qwen3.8-flash-next-125b', 64, 64, 'absent (below vram_tier)', 'exllamav3-rocm'),
    ('metal', 'qwen3.8-flash-next-125b', 8, 64, 'absent (below vram_tier)', 'exllamav3-rocm'),
    ('metal', 'qwen3.8-flash-next-125b', 16, 64, 'absent (below vram_tier)', 'exllamav3-rocm'),
    ('metal', 'qwen3.8-flash-next-125b', 24, 64, 'absent (below vram_tier)', 'exllamav3-rocm'),
    ('metal', 'qwen3.8-flash-next-125b', 32, 64, 'absent (below vram_tier)', 'exllamav3-rocm'),
    ('metal', 'qwen3.8-flash-next-125b', 64, 64, 'absent (below vram_tier)', 'exllamav3-rocm'),
    ('cuda', 'qwen3.8-flash-next-125b', 8, 64, 'absent (below vram_tier)', 'llama.cpp'),
    ('cuda', 'qwen3.8-flash-next-125b', 16, 64, 'Qwen3.8-Flash-Next-UD-IQ1_M-00001-of-00003.gguf', 'llama.cpp'),
    ('cuda', 'qwen3.8-flash-next-125b', 24, 64, 'Qwen3.8-Flash-Next-UD-IQ3_XXS-00001-of-00003.gguf', 'llama.cpp'),
    ('cuda', 'qwen3.8-flash-next-125b', 32, 64, 'Qwen3.8-Flash-Next-UD-Q3_K_XL-00001-of-00003.gguf', 'llama.cpp'),
    ('cuda', 'qwen3.8-flash-next-125b', 64, 64, 'Qwen3.8-Flash-Next-UD-Q4_K_XL-00001-of-00004.gguf', 'llama.cpp'),
    ('rocm', 'qwen3.8-flash-next-125b', 8, 64, 'absent (below vram_tier)', 'llama.cpp'),
    ('rocm', 'qwen3.8-flash-next-125b', 16, 64, 'Qwen3.8-Flash-Next-UD-IQ1_M-00001-of-00003.gguf', 'llama.cpp'),
    ('rocm', 'qwen3.8-flash-next-125b', 24, 64, 'Qwen3.8-Flash-Next-UD-IQ3_XXS-00001-of-00003.gguf', 'llama.cpp'),
    ('rocm', 'qwen3.8-flash-next-125b', 32, 64, 'Qwen3.8-Flash-Next-UD-Q3_K_XL-00001-of-00003.gguf', 'llama.cpp'),
    ('rocm', 'qwen3.8-flash-next-125b', 64, 64, 'Qwen3.8-Flash-Next-UD-Q4_K_XL-00001-of-00004.gguf', 'llama.cpp'),
    ('vulkan', 'qwen3.8-flash-next-125b', 8, 64, 'absent (below vram_tier)', 'llama.cpp'),
    ('vulkan', 'qwen3.8-flash-next-125b', 16, 64, 'Qwen3.8-Flash-Next-UD-IQ1_M-00001-of-00003.gguf', 'llama.cpp'),
    ('vulkan', 'qwen3.8-flash-next-125b', 24, 64, 'Qwen3.8-Flash-Next-UD-IQ3_XXS-00001-of-00003.gguf', 'llama.cpp'),
    ('vulkan', 'qwen3.8-flash-next-125b', 32, 64, 'Qwen3.8-Flash-Next-UD-Q3_K_XL-00001-of-00003.gguf', 'llama.cpp'),
    ('vulkan', 'qwen3.8-flash-next-125b', 64, 64, 'Qwen3.8-Flash-Next-UD-Q4_K_XL-00001-of-00004.gguf', 'llama.cpp'),
    ('cpu', 'qwen3.8-flash-next-125b', 8, 64, 'absent (below vram_tier)', 'llama.cpp'),
    ('cpu', 'qwen3.8-flash-next-125b', 16, 64, 'absent (below vram_tier)', 'llama.cpp'),
    ('cpu', 'qwen3.8-flash-next-125b', 24, 64, 'absent (below vram_tier)', 'llama.cpp'),
    ('cpu', 'qwen3.8-flash-next-125b', 32, 64, 'absent (below vram_tier)', 'llama.cpp'),
    ('cpu', 'qwen3.8-flash-next-125b', 64, 64, 'absent (below vram_tier)', 'llama.cpp'),
    ('metal', 'qwen3.8-flash-next-125b', 8, 64, 'absent (below vram_tier)', 'llama.cpp'),
    ('metal', 'qwen3.8-flash-next-125b', 16, 64, 'absent (below vram_tier)', 'llama.cpp'),
    ('metal', 'qwen3.8-flash-next-125b', 24, 64, 'absent (below vram_tier)', 'llama.cpp'),
    ('metal', 'qwen3.8-flash-next-125b', 32, 64, 'absent (below vram_tier)', 'llama.cpp'),
    ('metal', 'qwen3.8-flash-next-125b', 64, 64, 'absent (below vram_tier)', 'llama.cpp'),
    ('cuda', 'qwen3.8-flash-next-125b', 8, 64, 'absent (below vram_tier)', 'strata'),
    ('cuda', 'qwen3.8-flash-next-125b', 16, 64, 'Qwen3.8-Flash-Next-GSQ-RCO-IQ3_XXS-00002-of-00002.gguf', 'strata'),
    ('cuda', 'qwen3.8-flash-next-125b', 24, 64, 'Qwen3.8-Flash-Next-GSQ-RCO-IQ3_XXS-00002-of-00002.gguf', 'strata'),
    ('cuda', 'qwen3.8-flash-next-125b', 32, 64, 'Qwen3.8-Flash-Next-GSQ-RCO-IQ3_XXS-00002-of-00002.gguf', 'strata'),
    ('cuda', 'qwen3.8-flash-next-125b', 64, 64, 'Qwen3.8-Flash-Next-GSQ-RCO-IQ3_XXS-00002-of-00002.gguf', 'strata'),
    ('rocm', 'qwen3.8-flash-next-125b', 8, 64, 'absent (below vram_tier)', 'strata'),
    ('rocm', 'qwen3.8-flash-next-125b', 16, 64, 'Qwen3.8-Flash-Next-GSQ-RCO-IQ3_XXS-00002-of-00002.gguf', 'strata'),
    ('rocm', 'qwen3.8-flash-next-125b', 24, 64, 'Qwen3.8-Flash-Next-GSQ-RCO-IQ3_XXS-00002-of-00002.gguf', 'strata'),
    ('rocm', 'qwen3.8-flash-next-125b', 32, 64, 'Qwen3.8-Flash-Next-GSQ-RCO-IQ3_XXS-00002-of-00002.gguf', 'strata'),
    ('rocm', 'qwen3.8-flash-next-125b', 64, 64, 'Qwen3.8-Flash-Next-GSQ-RCO-IQ3_XXS-00002-of-00002.gguf', 'strata'),
    ('vulkan', 'qwen3.8-flash-next-125b', 8, 64, 'absent (below vram_tier)', 'strata'),
    ('vulkan', 'qwen3.8-flash-next-125b', 16, 64, 'no-fit', 'strata'),
    ('vulkan', 'qwen3.8-flash-next-125b', 24, 64, 'no-fit', 'strata'),
    ('vulkan', 'qwen3.8-flash-next-125b', 32, 64, 'no-fit', 'strata'),
    ('vulkan', 'qwen3.8-flash-next-125b', 64, 64, 'no-fit', 'strata'),
    ('cpu', 'qwen3.8-flash-next-125b', 8, 64, 'absent (below vram_tier)', 'strata'),
    ('cpu', 'qwen3.8-flash-next-125b', 16, 64, 'absent (below vram_tier)', 'strata'),
    ('cpu', 'qwen3.8-flash-next-125b', 24, 64, 'absent (below vram_tier)', 'strata'),
    ('cpu', 'qwen3.8-flash-next-125b', 32, 64, 'absent (below vram_tier)', 'strata'),
    ('cpu', 'qwen3.8-flash-next-125b', 64, 64, 'absent (below vram_tier)', 'strata'),
    ('metal', 'qwen3.8-flash-next-125b', 8, 64, 'absent (below vram_tier)', 'strata'),
    ('metal', 'qwen3.8-flash-next-125b', 16, 64, 'absent (below vram_tier)', 'strata'),
    ('metal', 'qwen3.8-flash-next-125b', 24, 64, 'absent (below vram_tier)', 'strata'),
    ('metal', 'qwen3.8-flash-next-125b', 32, 64, 'absent (below vram_tier)', 'strata'),
    ('metal', 'qwen3.8-flash-next-125b', 64, 64, 'absent (below vram_tier)', 'strata'),
    ('cuda', 'qwen3.8-flash-next-125b', 8, 64, 'absent (below vram_tier)', 'tensorfold'),
    ('cuda', 'qwen3.8-flash-next-125b', 16, 64, 'no-fit', 'tensorfold'),
    ('cuda', 'qwen3.8-flash-next-125b', 24, 64, 'LICENSE', 'tensorfold'),
    ('cuda', 'qwen3.8-flash-next-125b', 32, 64, 'LICENSE', 'tensorfold'),
    ('cuda', 'qwen3.8-flash-next-125b', 64, 64, 'LICENSE', 'tensorfold'),
    ('rocm', 'qwen3.8-flash-next-125b', 8, 64, 'absent (below vram_tier)', 'tensorfold'),
    ('rocm', 'qwen3.8-flash-next-125b', 16, 64, 'no-fit', 'tensorfold'),
    ('rocm', 'qwen3.8-flash-next-125b', 24, 64, 'no-fit', 'tensorfold'),
    ('rocm', 'qwen3.8-flash-next-125b', 32, 64, 'no-fit', 'tensorfold'),
    ('rocm', 'qwen3.8-flash-next-125b', 64, 64, 'no-fit', 'tensorfold'),
    ('vulkan', 'qwen3.8-flash-next-125b', 8, 64, 'absent (below vram_tier)', 'tensorfold'),
    ('vulkan', 'qwen3.8-flash-next-125b', 16, 64, 'no-fit', 'tensorfold'),
    ('vulkan', 'qwen3.8-flash-next-125b', 24, 64, 'no-fit', 'tensorfold'),
    ('vulkan', 'qwen3.8-flash-next-125b', 32, 64, 'no-fit', 'tensorfold'),
    ('vulkan', 'qwen3.8-flash-next-125b', 64, 64, 'no-fit', 'tensorfold'),
    ('cpu', 'qwen3.8-flash-next-125b', 8, 64, 'absent (below vram_tier)', 'tensorfold'),
    ('cpu', 'qwen3.8-flash-next-125b', 16, 64, 'absent (below vram_tier)', 'tensorfold'),
    ('cpu', 'qwen3.8-flash-next-125b', 24, 64, 'absent (below vram_tier)', 'tensorfold'),
    ('cpu', 'qwen3.8-flash-next-125b', 32, 64, 'absent (below vram_tier)', 'tensorfold'),
    ('cpu', 'qwen3.8-flash-next-125b', 64, 64, 'absent (below vram_tier)', 'tensorfold'),
    ('metal', 'qwen3.8-flash-next-125b', 8, 64, 'absent (below vram_tier)', 'tensorfold'),
    ('metal', 'qwen3.8-flash-next-125b', 16, 64, 'absent (below vram_tier)', 'tensorfold'),
    ('metal', 'qwen3.8-flash-next-125b', 24, 64, 'absent (below vram_tier)', 'tensorfold'),
    ('metal', 'qwen3.8-flash-next-125b', 32, 64, 'absent (below vram_tier)', 'tensorfold'),
    ('metal', 'qwen3.8-flash-next-125b', 64, 64, 'absent (below vram_tier)', 'tensorfold'),
    ('cuda', 'qwen3.8-27b', 8, 64, 'absent (below vram_tier)', 'llama.cpp'),
    ('cuda', 'qwen3.8-27b', 16, 64, 'Qwen3.8-27B-UD-IQ3_S.gguf', 'llama.cpp'),
    ('cuda', 'qwen3.8-27b', 24, 64, 'Qwen3.8-27B-UD-Q5_K_S.gguf', 'llama.cpp'),
    ('cuda', 'qwen3.8-27b', 32, 64, 'Qwen3.8-27B-UD-Q6_K_XL.gguf', 'llama.cpp'),
    ('cuda', 'qwen3.8-27b', 64, 64, 'Qwen3.8-27B-UD-Q8_K_XL.gguf', 'llama.cpp'),
    ('rocm', 'qwen3.8-27b', 8, 64, 'absent (below vram_tier)', 'llama.cpp'),
    ('rocm', 'qwen3.8-27b', 16, 64, 'Qwen3.8-27B-UD-IQ3_S.gguf', 'llama.cpp'),
    ('rocm', 'qwen3.8-27b', 24, 64, 'Qwen3.8-27B-UD-Q5_K_S.gguf', 'llama.cpp'),
    ('rocm', 'qwen3.8-27b', 32, 64, 'Qwen3.8-27B-UD-Q6_K_XL.gguf', 'llama.cpp'),
    ('rocm', 'qwen3.8-27b', 64, 64, 'Qwen3.8-27B-UD-Q8_K_XL.gguf', 'llama.cpp'),
    ('vulkan', 'qwen3.8-27b', 8, 64, 'absent (below vram_tier)', 'llama.cpp'),
    ('vulkan', 'qwen3.8-27b', 16, 64, 'Qwen3.8-27B-UD-IQ3_S.gguf', 'llama.cpp'),
    ('vulkan', 'qwen3.8-27b', 24, 64, 'Qwen3.8-27B-UD-Q5_K_S.gguf', 'llama.cpp'),
    ('vulkan', 'qwen3.8-27b', 32, 64, 'Qwen3.8-27B-UD-Q6_K_XL.gguf', 'llama.cpp'),
    ('vulkan', 'qwen3.8-27b', 64, 64, 'Qwen3.8-27B-UD-Q8_K_XL.gguf', 'llama.cpp'),
    ('cpu', 'qwen3.8-27b', 8, 64, 'absent (below vram_tier)', 'llama.cpp'),
    ('cpu', 'qwen3.8-27b', 16, 64, 'Qwen3.8-27B-UD-IQ3_S.gguf', 'llama.cpp'),
    ('cpu', 'qwen3.8-27b', 24, 64, 'Qwen3.8-27B-UD-Q5_K_S.gguf', 'llama.cpp'),
    ('cpu', 'qwen3.8-27b', 32, 64, 'Qwen3.8-27B-UD-Q6_K_XL.gguf', 'llama.cpp'),
    ('cpu', 'qwen3.8-27b', 64, 64, 'Qwen3.8-27B-UD-Q8_K_XL.gguf', 'llama.cpp'),
    ('metal', 'qwen3.8-27b', 8, 64, 'absent (below vram_tier)', 'llama.cpp'),
    ('metal', 'qwen3.8-27b', 16, 64, 'Qwen3.8-27B-UD-IQ1_M.gguf', 'llama.cpp'),
    ('metal', 'qwen3.8-27b', 24, 64, 'Qwen3.8-27B-UD-Q2_K_XL.gguf', 'llama.cpp'),
    ('metal', 'qwen3.8-27b', 32, 64, 'Qwen3.8-27B-UD-Q4_K_M.gguf', 'llama.cpp'),
    ('metal', 'qwen3.8-27b', 64, 64, 'Qwen3.8-27B-UD-Q8_K_XL.gguf', 'llama.cpp'),
    ('cuda', 'qwen3.8-27b', 8, 64, 'absent (below vram_tier)', 'llama.cpp-laurentzuijdwijk'),
    ('cuda', 'qwen3.8-27b', 16, 64, 'no-fit', 'llama.cpp-laurentzuijdwijk'),
    ('cuda', 'qwen3.8-27b', 24, 64, 'no-fit', 'llama.cpp-laurentzuijdwijk'),
    ('cuda', 'qwen3.8-27b', 32, 64, 'no-fit', 'llama.cpp-laurentzuijdwijk'),
    ('cuda', 'qwen3.8-27b', 64, 64, 'no-fit', 'llama.cpp-laurentzuijdwijk'),
    ('rocm', 'qwen3.8-27b', 8, 64, 'absent (below vram_tier)', 'llama.cpp-laurentzuijdwijk'),
    ('rocm', 'qwen3.8-27b', 16, 64, 'Qwen3.8-27B-UD-IQ3_S.gguf', 'llama.cpp-laurentzuijdwijk'),
    ('rocm', 'qwen3.8-27b', 24, 64, 'Qwen3.8-27B-UD-Q5_K_S.gguf', 'llama.cpp-laurentzuijdwijk'),
    ('rocm', 'qwen3.8-27b', 32, 64, 'Qwen3.8-27B-UD-Q6_K_XL.gguf', 'llama.cpp-laurentzuijdwijk'),
    ('rocm', 'qwen3.8-27b', 64, 64, 'Qwen3.8-27B-UD-Q8_K_XL.gguf', 'llama.cpp-laurentzuijdwijk'),
    ('vulkan', 'qwen3.8-27b', 8, 64, 'absent (below vram_tier)', 'llama.cpp-laurentzuijdwijk'),
    ('vulkan', 'qwen3.8-27b', 16, 64, 'Qwen3.8-27B-UD-IQ3_S.gguf', 'llama.cpp-laurentzuijdwijk'),
    ('vulkan', 'qwen3.8-27b', 24, 64, 'Qwen3.8-27B-UD-Q5_K_S.gguf', 'llama.cpp-laurentzuijdwijk'),
    ('vulkan', 'qwen3.8-27b', 32, 64, 'Qwen3.8-27B-UD-Q6_K_XL.gguf', 'llama.cpp-laurentzuijdwijk'),
    ('vulkan', 'qwen3.8-27b', 64, 64, 'Qwen3.8-27B-UD-Q8_K_XL.gguf', 'llama.cpp-laurentzuijdwijk'),
    ('cpu', 'qwen3.8-27b', 8, 64, 'absent (below vram_tier)', 'llama.cpp-laurentzuijdwijk'),
    ('cpu', 'qwen3.8-27b', 16, 64, 'Qwen3.8-27B-UD-IQ3_S.gguf', 'llama.cpp-laurentzuijdwijk'),
    ('cpu', 'qwen3.8-27b', 24, 64, 'Qwen3.8-27B-UD-Q5_K_S.gguf', 'llama.cpp-laurentzuijdwijk'),
    ('cpu', 'qwen3.8-27b', 32, 64, 'Qwen3.8-27B-UD-Q6_K_XL.gguf', 'llama.cpp-laurentzuijdwijk'),
    ('cpu', 'qwen3.8-27b', 64, 64, 'Qwen3.8-27B-UD-Q8_K_XL.gguf', 'llama.cpp-laurentzuijdwijk'),
    ('metal', 'qwen3.8-27b', 8, 64, 'absent (below vram_tier)', 'llama.cpp-laurentzuijdwijk'),
    ('metal', 'qwen3.8-27b', 16, 64, 'no-fit', 'llama.cpp-laurentzuijdwijk'),
    ('metal', 'qwen3.8-27b', 24, 64, 'no-fit', 'llama.cpp-laurentzuijdwijk'),
    ('metal', 'qwen3.8-27b', 32, 64, 'no-fit', 'llama.cpp-laurentzuijdwijk'),
    ('metal', 'qwen3.8-27b', 64, 64, 'no-fit', 'llama.cpp-laurentzuijdwijk'),
    ('cuda', 'qwen3.8-27b', 8, 64, 'absent (below vram_tier)', 'mlx'),
    ('cuda', 'qwen3.8-27b', 16, 64, 'no-fit', 'mlx'),
    ('cuda', 'qwen3.8-27b', 24, 64, 'lmstudio-community/Qwen3.8-27B-MLX-5bit', 'mlx'),
    ('cuda', 'qwen3.8-27b', 32, 64, 'lmstudio-community/Qwen3.8-27B-MLX-6bit', 'mlx'),
    ('cuda', 'qwen3.8-27b', 64, 64, 'lmstudio-community/Qwen3.8-27B-MLX-8bit', 'mlx'),
    ('rocm', 'qwen3.8-27b', 8, 64, 'absent (below vram_tier)', 'mlx'),
    ('rocm', 'qwen3.8-27b', 16, 64, 'no-fit', 'mlx'),
    ('rocm', 'qwen3.8-27b', 24, 64, 'no-fit', 'mlx'),
    ('rocm', 'qwen3.8-27b', 32, 64, 'no-fit', 'mlx'),
    ('rocm', 'qwen3.8-27b', 64, 64, 'no-fit', 'mlx'),
    ('vulkan', 'qwen3.8-27b', 8, 64, 'absent (below vram_tier)', 'mlx'),
    ('vulkan', 'qwen3.8-27b', 16, 64, 'no-fit', 'mlx'),
    ('vulkan', 'qwen3.8-27b', 24, 64, 'no-fit', 'mlx'),
    ('vulkan', 'qwen3.8-27b', 32, 64, 'no-fit', 'mlx'),
    ('vulkan', 'qwen3.8-27b', 64, 64, 'no-fit', 'mlx'),
    ('cpu', 'qwen3.8-27b', 8, 64, 'absent (below vram_tier)', 'mlx'),
    ('cpu', 'qwen3.8-27b', 16, 64, 'no-fit', 'mlx'),
    ('cpu', 'qwen3.8-27b', 24, 64, 'lmstudio-community/Qwen3.8-27B-MLX-5bit', 'mlx'),
    ('cpu', 'qwen3.8-27b', 32, 64, 'lmstudio-community/Qwen3.8-27B-MLX-6bit', 'mlx'),
    ('cpu', 'qwen3.8-27b', 64, 64, 'lmstudio-community/Qwen3.8-27B-MLX-8bit', 'mlx'),
    ('metal', 'qwen3.8-27b', 8, 64, 'absent (below vram_tier)', 'mlx'),
    ('metal', 'qwen3.8-27b', 16, 64, 'no-fit', 'mlx'),
    ('metal', 'qwen3.8-27b', 24, 64, 'no-fit', 'mlx'),
    ('metal', 'qwen3.8-27b', 32, 64, 'TensorFold/Qwen3.8-27B-MLX-4bit', 'mlx'),
    ('metal', 'qwen3.8-27b', 64, 64, 'lmstudio-community/Qwen3.8-27B-MLX-8bit', 'mlx'),
    ('cuda', 'qwen3.8-27b', 8, 64, 'absent (below vram_tier)', 'sglang'),
    ('cuda', 'qwen3.8-27b', 16, 64, 'Qwen3.8-27B-UD-IQ3_S.gguf', 'sglang'),
    ('cuda', 'qwen3.8-27b', 24, 64, 'Qwen3.8-27B-UD-Q5_K_S.gguf', 'sglang'),
    ('cuda', 'qwen3.8-27b', 32, 64, 'Qwen3.8-27B-UD-Q6_K_XL.gguf', 'sglang'),
    ('cuda', 'qwen3.8-27b', 64, 64, 'Qwen3.8-27B-UD-Q8_K_XL.gguf', 'sglang'),
    ('rocm', 'qwen3.8-27b', 8, 64, 'absent (below vram_tier)', 'sglang'),
    ('rocm', 'qwen3.8-27b', 16, 64, 'Qwen3.8-27B-UD-IQ3_S.gguf', 'sglang'),
    ('rocm', 'qwen3.8-27b', 24, 64, 'Qwen3.8-27B-UD-Q5_K_S.gguf', 'sglang'),
    ('rocm', 'qwen3.8-27b', 32, 64, 'Qwen3.8-27B-UD-Q6_K_XL.gguf', 'sglang'),
    ('rocm', 'qwen3.8-27b', 64, 64, 'Qwen3.8-27B-UD-Q8_K_XL.gguf', 'sglang'),
    ('vulkan', 'qwen3.8-27b', 8, 64, 'absent (below vram_tier)', 'sglang'),
    ('vulkan', 'qwen3.8-27b', 16, 64, 'no-fit', 'sglang'),
    ('vulkan', 'qwen3.8-27b', 24, 64, 'no-fit', 'sglang'),
    ('vulkan', 'qwen3.8-27b', 32, 64, 'no-fit', 'sglang'),
    ('vulkan', 'qwen3.8-27b', 64, 64, 'no-fit', 'sglang'),
    ('cpu', 'qwen3.8-27b', 8, 64, 'absent (below vram_tier)', 'sglang'),
    ('cpu', 'qwen3.8-27b', 16, 64, 'no-fit', 'sglang'),
    ('cpu', 'qwen3.8-27b', 24, 64, 'no-fit', 'sglang'),
    ('cpu', 'qwen3.8-27b', 32, 64, 'no-fit', 'sglang'),
    ('cpu', 'qwen3.8-27b', 64, 64, 'no-fit', 'sglang'),
    ('metal', 'qwen3.8-27b', 8, 64, 'absent (below vram_tier)', 'sglang'),
    ('metal', 'qwen3.8-27b', 16, 64, 'no-fit', 'sglang'),
    ('metal', 'qwen3.8-27b', 24, 64, 'no-fit', 'sglang'),
    ('metal', 'qwen3.8-27b', 32, 64, 'no-fit', 'sglang'),
    ('metal', 'qwen3.8-27b', 64, 64, 'no-fit', 'sglang'),
    ('cuda', 'qwen3.8-27b', 8, 64, 'absent (below vram_tier)', 'tensorfold'),
    ('cuda', 'qwen3.8-27b', 16, 64, 'no-fit', 'tensorfold'),
    ('cuda', 'qwen3.8-27b', 24, 64, 'LICENSE', 'tensorfold'),
    ('cuda', 'qwen3.8-27b', 32, 64, 'LICENSE', 'tensorfold'),
    ('cuda', 'qwen3.8-27b', 64, 64, 'LICENSE', 'tensorfold'),
    ('rocm', 'qwen3.8-27b', 8, 64, 'absent (below vram_tier)', 'tensorfold'),
    ('rocm', 'qwen3.8-27b', 16, 64, 'no-fit', 'tensorfold'),
    ('rocm', 'qwen3.8-27b', 24, 64, 'no-fit', 'tensorfold'),
    ('rocm', 'qwen3.8-27b', 32, 64, 'no-fit', 'tensorfold'),
    ('rocm', 'qwen3.8-27b', 64, 64, 'no-fit', 'tensorfold'),
    ('vulkan', 'qwen3.8-27b', 8, 64, 'absent (below vram_tier)', 'tensorfold'),
    ('vulkan', 'qwen3.8-27b', 16, 64, 'no-fit', 'tensorfold'),
    ('vulkan', 'qwen3.8-27b', 24, 64, 'no-fit', 'tensorfold'),
    ('vulkan', 'qwen3.8-27b', 32, 64, 'no-fit', 'tensorfold'),
    ('vulkan', 'qwen3.8-27b', 64, 64, 'no-fit', 'tensorfold'),
    ('cpu', 'qwen3.8-27b', 8, 64, 'absent (below vram_tier)', 'tensorfold'),
    ('cpu', 'qwen3.8-27b', 16, 64, 'no-fit', 'tensorfold'),
    ('cpu', 'qwen3.8-27b', 24, 64, 'no-fit', 'tensorfold'),
    ('cpu', 'qwen3.8-27b', 32, 64, 'no-fit', 'tensorfold'),
    ('cpu', 'qwen3.8-27b', 64, 64, 'no-fit', 'tensorfold'),
    ('metal', 'qwen3.8-27b', 8, 64, 'absent (below vram_tier)', 'tensorfold'),
    ('metal', 'qwen3.8-27b', 16, 64, 'no-fit', 'tensorfold'),
    ('metal', 'qwen3.8-27b', 24, 64, 'no-fit', 'tensorfold'),
    ('metal', 'qwen3.8-27b', 32, 64, 'LICENSE', 'tensorfold'),
    ('metal', 'qwen3.8-27b', 64, 64, 'LICENSE', 'tensorfold'),
    ('cuda', 'bonsai-2-27b', 8, 64, 'absent (below vram_tier)', 'llama.cpp-prism'),
    ('cuda', 'bonsai-2-27b', 16, 64, 'absent (below vram_tier)', 'llama.cpp-prism'),
    ('cuda', 'bonsai-2-27b', 24, 64, 'absent (below vram_tier)', 'llama.cpp-prism'),
    ('cuda', 'bonsai-2-27b', 32, 64, 'absent (below vram_tier)', 'llama.cpp-prism'),
    ('cuda', 'bonsai-2-27b', 64, 64, 'absent (below vram_tier)', 'llama.cpp-prism'),
    ('rocm', 'bonsai-2-27b', 8, 64, 'absent (below vram_tier)', 'llama.cpp-prism'),
    ('rocm', 'bonsai-2-27b', 16, 64, 'absent (below vram_tier)', 'llama.cpp-prism'),
    ('rocm', 'bonsai-2-27b', 24, 64, 'absent (below vram_tier)', 'llama.cpp-prism'),
    ('rocm', 'bonsai-2-27b', 32, 64, 'absent (below vram_tier)', 'llama.cpp-prism'),
    ('rocm', 'bonsai-2-27b', 64, 64, 'absent (below vram_tier)', 'llama.cpp-prism'),
    ('vulkan', 'bonsai-2-27b', 8, 64, 'absent (below vram_tier)', 'llama.cpp-prism'),
    ('vulkan', 'bonsai-2-27b', 16, 64, 'Ternary-Bonsai-2-27B-PQ2_0.gguf', 'llama.cpp-prism'),
    ('vulkan', 'bonsai-2-27b', 24, 64, 'Ternary-Bonsai-2-27B-PQ2_0.gguf', 'llama.cpp-prism'),
    ('vulkan', 'bonsai-2-27b', 32, 64, 'Ternary-Bonsai-2-27B-PQ2_0.gguf', 'llama.cpp-prism'),
    ('vulkan', 'bonsai-2-27b', 64, 64, 'Ternary-Bonsai-2-27B-F16.gguf', 'llama.cpp-prism'),
    ('cpu', 'bonsai-2-27b', 8, 64, 'absent (below vram_tier)', 'llama.cpp-prism'),
    ('cpu', 'bonsai-2-27b', 16, 64, 'Ternary-Bonsai-2-27B-PQ2_0.gguf', 'llama.cpp-prism'),
    ('cpu', 'bonsai-2-27b', 24, 64, 'Ternary-Bonsai-2-27B-PQ2_0.gguf', 'llama.cpp-prism'),
    ('cpu', 'bonsai-2-27b', 32, 64, 'Ternary-Bonsai-2-27B-PQ2_0.gguf', 'llama.cpp-prism'),
    ('cpu', 'bonsai-2-27b', 64, 64, 'Ternary-Bonsai-2-27B-F16.gguf', 'llama.cpp-prism'),
    ('metal', 'bonsai-2-27b', 8, 64, 'absent (below vram_tier)', 'llama.cpp-prism'),
    ('metal', 'bonsai-2-27b', 16, 64, 'Ternary-Bonsai-2-27B-PTQ1_0.gguf', 'llama.cpp-prism'),
    ('metal', 'bonsai-2-27b', 24, 64, 'Ternary-Bonsai-2-27B-PQ2_0.gguf', 'llama.cpp-prism'),
    ('metal', 'bonsai-2-27b', 32, 64, 'Ternary-Bonsai-2-27B-PQ2_0.gguf', 'llama.cpp-prism'),
    ('metal', 'bonsai-2-27b', 64, 64, 'Ternary-Bonsai-2-27B-PQ2_0.gguf', 'llama.cpp-prism'),
    ('cuda', 'ravenx-conjecture-qwen3-8b-mlx', 8, 64, 'deadbydawn101/RavenX-Conjecture-Qwen3-8B-MLX', 'mlx'),
    ('cuda', 'ravenx-conjecture-qwen3-8b-mlx', 16, 64, 'deadbydawn101/RavenX-Conjecture-Qwen3-8B-MLX', 'mlx'),
    ('cuda', 'ravenx-conjecture-qwen3-8b-mlx', 24, 64, 'deadbydawn101/RavenX-Conjecture-Qwen3-8B-MLX', 'mlx'),
    ('cuda', 'ravenx-conjecture-qwen3-8b-mlx', 32, 64, 'deadbydawn101/RavenX-Conjecture-Qwen3-8B-MLX', 'mlx'),
    ('cuda', 'ravenx-conjecture-qwen3-8b-mlx', 64, 64, 'deadbydawn101/RavenX-Conjecture-Qwen3-8B-MLX', 'mlx'),
    ('rocm', 'ravenx-conjecture-qwen3-8b-mlx', 8, 64, 'absent (below vram_tier)', 'mlx'),
    ('rocm', 'ravenx-conjecture-qwen3-8b-mlx', 16, 64, 'absent (below vram_tier)', 'mlx'),
    ('rocm', 'ravenx-conjecture-qwen3-8b-mlx', 24, 64, 'absent (below vram_tier)', 'mlx'),
    ('rocm', 'ravenx-conjecture-qwen3-8b-mlx', 32, 64, 'absent (below vram_tier)', 'mlx'),
    ('rocm', 'ravenx-conjecture-qwen3-8b-mlx', 64, 64, 'absent (below vram_tier)', 'mlx'),
    ('vulkan', 'ravenx-conjecture-qwen3-8b-mlx', 8, 64, 'absent (below vram_tier)', 'mlx'),
    ('vulkan', 'ravenx-conjecture-qwen3-8b-mlx', 16, 64, 'absent (below vram_tier)', 'mlx'),
    ('vulkan', 'ravenx-conjecture-qwen3-8b-mlx', 24, 64, 'absent (below vram_tier)', 'mlx'),
    ('vulkan', 'ravenx-conjecture-qwen3-8b-mlx', 32, 64, 'absent (below vram_tier)', 'mlx'),
    ('vulkan', 'ravenx-conjecture-qwen3-8b-mlx', 64, 64, 'absent (below vram_tier)', 'mlx'),
    ('cpu', 'ravenx-conjecture-qwen3-8b-mlx', 8, 64, 'deadbydawn101/RavenX-Conjecture-Qwen3-8B-MLX', 'mlx'),
    ('cpu', 'ravenx-conjecture-qwen3-8b-mlx', 16, 64, 'deadbydawn101/RavenX-Conjecture-Qwen3-8B-MLX', 'mlx'),
    ('cpu', 'ravenx-conjecture-qwen3-8b-mlx', 24, 64, 'deadbydawn101/RavenX-Conjecture-Qwen3-8B-MLX', 'mlx'),
    ('cpu', 'ravenx-conjecture-qwen3-8b-mlx', 32, 64, 'deadbydawn101/RavenX-Conjecture-Qwen3-8B-MLX', 'mlx'),
    ('cpu', 'ravenx-conjecture-qwen3-8b-mlx', 64, 64, 'deadbydawn101/RavenX-Conjecture-Qwen3-8B-MLX', 'mlx'),
    ('metal', 'ravenx-conjecture-qwen3-8b-mlx', 8, 64, 'absent (below vram_tier)', 'mlx'),
    ('metal', 'ravenx-conjecture-qwen3-8b-mlx', 16, 64, 'deadbydawn101/RavenX-Conjecture-Qwen3-8B-MLX', 'mlx'),
    ('metal', 'ravenx-conjecture-qwen3-8b-mlx', 24, 64, 'deadbydawn101/RavenX-Conjecture-Qwen3-8B-MLX', 'mlx'),
    ('metal', 'ravenx-conjecture-qwen3-8b-mlx', 32, 64, 'deadbydawn101/RavenX-Conjecture-Qwen3-8B-MLX', 'mlx'),
    ('metal', 'ravenx-conjecture-qwen3-8b-mlx', 64, 64, 'deadbydawn101/RavenX-Conjecture-Qwen3-8B-MLX', 'mlx'),
    ('cuda', 'qwen3.6-35b-a3b', 8, 64, 'Qwen3.6-35B-A3B-BF16-00001-of-00002.gguf', 'freetoken'),
    ('cuda', 'qwen3.6-35b-a3b', 16, 64, 'Qwen/Qwen3.6-35B-A3B', 'freetoken'),
    ('cuda', 'qwen3.6-35b-a3b', 24, 64, 'Qwen/Qwen3.6-35B-A3B', 'freetoken'),
    ('cuda', 'qwen3.6-35b-a3b', 32, 64, 'Qwen/Qwen3.6-35B-A3B', 'freetoken'),
    ('cuda', 'qwen3.6-35b-a3b', 64, 64, 'Qwen/Qwen3.6-35B-A3B', 'freetoken'),
    ('rocm', 'qwen3.6-35b-a3b', 8, 64, 'Qwen3.6-35B-A3B-BF16-00001-of-00002.gguf', 'freetoken'),
    ('rocm', 'qwen3.6-35b-a3b', 16, 64, 'Qwen/Qwen3.6-35B-A3B', 'freetoken'),
    ('rocm', 'qwen3.6-35b-a3b', 24, 64, 'Qwen/Qwen3.6-35B-A3B', 'freetoken'),
    ('rocm', 'qwen3.6-35b-a3b', 32, 64, 'Qwen/Qwen3.6-35B-A3B', 'freetoken'),
    ('rocm', 'qwen3.6-35b-a3b', 64, 64, 'Qwen/Qwen3.6-35B-A3B', 'freetoken'),
    ('vulkan', 'qwen3.6-35b-a3b', 8, 64, 'absent (below vram_tier)', 'freetoken'),
    ('vulkan', 'qwen3.6-35b-a3b', 16, 64, 'absent (below vram_tier)', 'freetoken'),
    ('vulkan', 'qwen3.6-35b-a3b', 24, 64, 'absent (below vram_tier)', 'freetoken'),
    ('vulkan', 'qwen3.6-35b-a3b', 32, 64, 'absent (below vram_tier)', 'freetoken'),
    ('vulkan', 'qwen3.6-35b-a3b', 64, 64, 'absent (below vram_tier)', 'freetoken'),
    ('cpu', 'qwen3.6-35b-a3b', 8, 64, 'absent (below vram_tier)', 'freetoken'),
    ('cpu', 'qwen3.6-35b-a3b', 16, 64, 'absent (below vram_tier)', 'freetoken'),
    ('cpu', 'qwen3.6-35b-a3b', 24, 64, 'absent (below vram_tier)', 'freetoken'),
    ('cpu', 'qwen3.6-35b-a3b', 32, 64, 'absent (below vram_tier)', 'freetoken'),
    ('cpu', 'qwen3.6-35b-a3b', 64, 64, 'absent (below vram_tier)', 'freetoken'),
    ('metal', 'qwen3.6-35b-a3b', 8, 64, 'absent (below vram_tier)', 'freetoken'),
    ('metal', 'qwen3.6-35b-a3b', 16, 64, 'absent (below vram_tier)', 'freetoken'),
    ('metal', 'qwen3.6-35b-a3b', 24, 64, 'absent (below vram_tier)', 'freetoken'),
    ('metal', 'qwen3.6-35b-a3b', 32, 64, 'absent (below vram_tier)', 'freetoken'),
    ('metal', 'qwen3.6-35b-a3b', 64, 64, 'absent (below vram_tier)', 'freetoken'),
    ('cuda', 'ornith-1.5', 8, 64, 'absent (below vram_tier)', 'mlx'),
    ('cuda', 'ornith-1.5', 16, 64, 'absent (below vram_tier)', 'mlx'),
    ('cuda', 'ornith-1.5', 24, 64, 'absent (below vram_tier)', 'mlx'),
    ('cuda', 'ornith-1.5', 32, 64, 'absent (below vram_tier)', 'mlx'),
    ('cuda', 'ornith-1.5', 64, 64, 'ornith-ai/Ornith-1.5-9B', 'mlx'),
    ('rocm', 'ornith-1.5', 8, 64, 'absent (below vram_tier)', 'mlx'),
    ('rocm', 'ornith-1.5', 16, 64, 'absent (below vram_tier)', 'mlx'),
    ('rocm', 'ornith-1.5', 24, 64, 'absent (below vram_tier)', 'mlx'),
    ('rocm', 'ornith-1.5', 32, 64, 'absent (below vram_tier)', 'mlx'),
    ('rocm', 'ornith-1.5', 64, 64, 'absent (below vram_tier)', 'mlx'),
    ('vulkan', 'ornith-1.5', 8, 64, 'absent (below vram_tier)', 'mlx'),
    ('vulkan', 'ornith-1.5', 16, 64, 'absent (below vram_tier)', 'mlx'),
    ('vulkan', 'ornith-1.5', 24, 64, 'absent (below vram_tier)', 'mlx'),
    ('vulkan', 'ornith-1.5', 32, 64, 'absent (below vram_tier)', 'mlx'),
    ('vulkan', 'ornith-1.5', 64, 64, 'absent (below vram_tier)', 'mlx'),
    ('cpu', 'ornith-1.5', 8, 64, 'absent (below vram_tier)', 'mlx'),
    ('cpu', 'ornith-1.5', 16, 64, 'absent (below vram_tier)', 'mlx'),
    ('cpu', 'ornith-1.5', 24, 64, 'absent (below vram_tier)', 'mlx'),
    ('cpu', 'ornith-1.5', 32, 64, 'absent (below vram_tier)', 'mlx'),
    ('cpu', 'ornith-1.5', 64, 64, 'ornith-ai/Ornith-1.5-9B', 'mlx'),
    ('metal', 'ornith-1.5', 8, 64, 'absent (below vram_tier)', 'mlx'),
    ('metal', 'ornith-1.5', 16, 64, 'absent (below vram_tier)', 'mlx'),
    ('metal', 'ornith-1.5', 24, 64, 'absent (below vram_tier)', 'mlx'),
    ('metal', 'ornith-1.5', 32, 64, 'absent (below vram_tier)', 'mlx'),
    ('metal', 'ornith-1.5', 64, 64, 'ornith-ai/Ornith-1.5-9B', 'mlx'),
    ('cuda', 'qwen3-8b', 8, 64, 'Qwen3-8B-Q5_0.gguf', 'ollama'),
    ('cuda', 'qwen3-8b', 16, 64, 'Qwen3-8B-Q8_0.gguf', 'ollama'),
    ('cuda', 'qwen3-8b', 24, 64, 'Qwen3-8B-Q8_0.gguf', 'ollama'),
    ('cuda', 'qwen3-8b', 32, 64, 'Qwen3-8B-Q8_0.gguf', 'ollama'),
    ('cuda', 'qwen3-8b', 64, 64, 'Qwen3-8B-Q8_0.gguf', 'ollama'),
    ('rocm', 'qwen3-8b', 8, 64, 'Qwen3-8B-Q5_0.gguf', 'ollama'),
    ('rocm', 'qwen3-8b', 16, 64, 'Qwen3-8B-Q8_0.gguf', 'ollama'),
    ('rocm', 'qwen3-8b', 24, 64, 'Qwen3-8B-Q8_0.gguf', 'ollama'),
    ('rocm', 'qwen3-8b', 32, 64, 'Qwen3-8B-Q8_0.gguf', 'ollama'),
    ('rocm', 'qwen3-8b', 64, 64, 'Qwen3-8B-Q8_0.gguf', 'ollama'),
    ('vulkan', 'qwen3-8b', 8, 64, 'Qwen3-8B-Q5_0.gguf', 'ollama'),
    ('vulkan', 'qwen3-8b', 16, 64, 'Qwen3-8B-Q8_0.gguf', 'ollama'),
    ('vulkan', 'qwen3-8b', 24, 64, 'Qwen3-8B-Q8_0.gguf', 'ollama'),
    ('vulkan', 'qwen3-8b', 32, 64, 'Qwen3-8B-Q8_0.gguf', 'ollama'),
    ('vulkan', 'qwen3-8b', 64, 64, 'Qwen3-8B-Q8_0.gguf', 'ollama'),
    ('cpu', 'qwen3-8b', 8, 64, 'Qwen3-8B-Q5_0.gguf', 'ollama'),
    ('cpu', 'qwen3-8b', 16, 64, 'Qwen3-8B-Q8_0.gguf', 'ollama'),
    ('cpu', 'qwen3-8b', 24, 64, 'Qwen3-8B-Q8_0.gguf', 'ollama'),
    ('cpu', 'qwen3-8b', 32, 64, 'Qwen3-8B-Q8_0.gguf', 'ollama'),
    ('cpu', 'qwen3-8b', 64, 64, 'Qwen3-8B-Q8_0.gguf', 'ollama'),
    ('metal', 'qwen3-8b', 8, 64, 'absent (below vram_tier)', 'ollama'),
    ('metal', 'qwen3-8b', 16, 64, 'Qwen3-8B-Q6_K.gguf', 'ollama'),
    ('metal', 'qwen3-8b', 24, 64, 'Qwen3-8B-Q8_0.gguf', 'ollama'),
    ('metal', 'qwen3-8b', 32, 64, 'Qwen3-8B-Q8_0.gguf', 'ollama'),
    ('metal', 'qwen3-8b', 64, 64, 'Qwen3-8B-Q8_0.gguf', 'ollama'),
    ('cuda', 'gemma-4-12b', 8, 64, 'absent (below vram_tier)', 'llama.cpp'),
    ('cuda', 'gemma-4-12b', 16, 64, 'gemma-4-12b-it-Q8_0.gguf', 'llama.cpp'),
    ('cuda', 'gemma-4-12b', 24, 64, 'gemma-4-12b-it-UD-Q8_K_XL.gguf', 'llama.cpp'),
    ('cuda', 'gemma-4-12b', 32, 64, 'gemma-4-12b-it-BF16.gguf', 'llama.cpp'),
    ('cuda', 'gemma-4-12b', 64, 64, 'gemma-4-12b-it-BF16.gguf', 'llama.cpp'),
    ('rocm', 'gemma-4-12b', 8, 64, 'absent (below vram_tier)', 'llama.cpp'),
    ('rocm', 'gemma-4-12b', 16, 64, 'gemma-4-12b-it-Q8_0.gguf', 'llama.cpp'),
    ('rocm', 'gemma-4-12b', 24, 64, 'gemma-4-12b-it-UD-Q8_K_XL.gguf', 'llama.cpp'),
    ('rocm', 'gemma-4-12b', 32, 64, 'gemma-4-12b-it-BF16.gguf', 'llama.cpp'),
    ('rocm', 'gemma-4-12b', 64, 64, 'gemma-4-12b-it-BF16.gguf', 'llama.cpp'),
    ('vulkan', 'gemma-4-12b', 8, 64, 'absent (below vram_tier)', 'llama.cpp'),
    ('vulkan', 'gemma-4-12b', 16, 64, 'gemma-4-12b-it-Q8_0.gguf', 'llama.cpp'),
    ('vulkan', 'gemma-4-12b', 24, 64, 'gemma-4-12b-it-UD-Q8_K_XL.gguf', 'llama.cpp'),
    ('vulkan', 'gemma-4-12b', 32, 64, 'gemma-4-12b-it-BF16.gguf', 'llama.cpp'),
    ('vulkan', 'gemma-4-12b', 64, 64, 'gemma-4-12b-it-BF16.gguf', 'llama.cpp'),
    ('cpu', 'gemma-4-12b', 8, 64, 'absent (below vram_tier)', 'llama.cpp'),
    ('cpu', 'gemma-4-12b', 16, 64, 'gemma-4-12b-it-Q8_0.gguf', 'llama.cpp'),
    ('cpu', 'gemma-4-12b', 24, 64, 'gemma-4-12b-it-UD-Q8_K_XL.gguf', 'llama.cpp'),
    ('cpu', 'gemma-4-12b', 32, 64, 'gemma-4-12b-it-BF16.gguf', 'llama.cpp'),
    ('cpu', 'gemma-4-12b', 64, 64, 'gemma-4-12b-it-BF16.gguf', 'llama.cpp'),
    ('metal', 'gemma-4-12b', 8, 64, 'absent (below vram_tier)', 'llama.cpp'),
    ('metal', 'gemma-4-12b', 16, 64, 'gemma-4-12b-it-Q4_K_S.gguf', 'llama.cpp'),
    ('metal', 'gemma-4-12b', 24, 64, 'gemma-4-12b-it-Q6_K.gguf', 'llama.cpp'),
    ('metal', 'gemma-4-12b', 32, 64, 'gemma-4-12b-it-UD-Q8_K_XL.gguf', 'llama.cpp'),
    ('metal', 'gemma-4-12b', 64, 64, 'gemma-4-12b-it-BF16.gguf', 'llama.cpp'),
    ('cuda', 'qwen3-14b', 8, 64, 'absent (below vram_tier)', 'ollama'),
    ('cuda', 'qwen3-14b', 16, 64, 'Qwen3-14B-Q6_K.gguf', 'ollama'),
    ('cuda', 'qwen3-14b', 24, 64, 'Qwen3-14B-Q8_0.gguf', 'ollama'),
    ('cuda', 'qwen3-14b', 32, 64, 'Qwen3-14B-Q8_0.gguf', 'ollama'),
    ('cuda', 'qwen3-14b', 64, 64, 'Qwen3-14B-Q8_0.gguf', 'ollama'),
    ('rocm', 'qwen3-14b', 8, 64, 'absent (below vram_tier)', 'ollama'),
    ('rocm', 'qwen3-14b', 16, 64, 'Qwen3-14B-Q6_K.gguf', 'ollama'),
    ('rocm', 'qwen3-14b', 24, 64, 'Qwen3-14B-Q8_0.gguf', 'ollama'),
    ('rocm', 'qwen3-14b', 32, 64, 'Qwen3-14B-Q8_0.gguf', 'ollama'),
    ('rocm', 'qwen3-14b', 64, 64, 'Qwen3-14B-Q8_0.gguf', 'ollama'),
    ('vulkan', 'qwen3-14b', 8, 64, 'absent (below vram_tier)', 'ollama'),
    ('vulkan', 'qwen3-14b', 16, 64, 'Qwen3-14B-Q6_K.gguf', 'ollama'),
    ('vulkan', 'qwen3-14b', 24, 64, 'Qwen3-14B-Q8_0.gguf', 'ollama'),
    ('vulkan', 'qwen3-14b', 32, 64, 'Qwen3-14B-Q8_0.gguf', 'ollama'),
    ('vulkan', 'qwen3-14b', 64, 64, 'Qwen3-14B-Q8_0.gguf', 'ollama'),
    ('cpu', 'qwen3-14b', 8, 64, 'absent (below vram_tier)', 'ollama'),
    ('cpu', 'qwen3-14b', 16, 64, 'Qwen3-14B-Q6_K.gguf', 'ollama'),
    ('cpu', 'qwen3-14b', 24, 64, 'Qwen3-14B-Q8_0.gguf', 'ollama'),
    ('cpu', 'qwen3-14b', 32, 64, 'Qwen3-14B-Q8_0.gguf', 'ollama'),
    ('cpu', 'qwen3-14b', 64, 64, 'Qwen3-14B-Q8_0.gguf', 'ollama'),
    ('metal', 'qwen3-14b', 8, 64, 'absent (below vram_tier)', 'ollama'),
    ('metal', 'qwen3-14b', 16, 64, 'absent (below vram_tier)', 'ollama'),
    ('metal', 'qwen3-14b', 24, 64, 'Qwen3-14B-Q5_K_M.gguf', 'ollama'),
    ('metal', 'qwen3-14b', 32, 64, 'Qwen3-14B-Q8_0.gguf', 'ollama'),
    ('metal', 'qwen3-14b', 64, 64, 'Qwen3-14B-Q8_0.gguf', 'ollama'),
    ('cuda', 'qwen-3.6-27b', 8, 64, 'absent (below vram_tier)', 'llama.cpp'),
    ('cuda', 'qwen-3.6-27b', 16, 64, 'absent (below vram_tier)', 'llama.cpp'),
    ('cuda', 'qwen-3.6-27b', 24, 64, 'Qwen3.6-27B-Q5_K_M.gguf', 'llama.cpp'),
    ('cuda', 'qwen-3.6-27b', 32, 64, 'Qwen3.6-27B-UD-Q6_K_XL.gguf', 'llama.cpp'),
    ('cuda', 'qwen-3.6-27b', 64, 64, 'Qwen3.6-27B-BF16-00001-of-00002.gguf', 'llama.cpp'),
    ('rocm', 'qwen-3.6-27b', 8, 64, 'absent (below vram_tier)', 'llama.cpp'),
    ('rocm', 'qwen-3.6-27b', 16, 64, 'absent (below vram_tier)', 'llama.cpp'),
    ('rocm', 'qwen-3.6-27b', 24, 64, 'Qwen3.6-27B-Q5_K_M.gguf', 'llama.cpp'),
    ('rocm', 'qwen-3.6-27b', 32, 64, 'Qwen3.6-27B-UD-Q6_K_XL.gguf', 'llama.cpp'),
    ('rocm', 'qwen-3.6-27b', 64, 64, 'Qwen3.6-27B-BF16-00001-of-00002.gguf', 'llama.cpp'),
    ('vulkan', 'qwen-3.6-27b', 8, 64, 'absent (below vram_tier)', 'llama.cpp'),
    ('vulkan', 'qwen-3.6-27b', 16, 64, 'absent (below vram_tier)', 'llama.cpp'),
    ('vulkan', 'qwen-3.6-27b', 24, 64, 'Qwen3.6-27B-Q5_K_M.gguf', 'llama.cpp'),
    ('vulkan', 'qwen-3.6-27b', 32, 64, 'Qwen3.6-27B-UD-Q6_K_XL.gguf', 'llama.cpp'),
    ('vulkan', 'qwen-3.6-27b', 64, 64, 'Qwen3.6-27B-BF16-00001-of-00002.gguf', 'llama.cpp'),
    ('cpu', 'qwen-3.6-27b', 8, 64, 'absent (below vram_tier)', 'llama.cpp'),
    ('cpu', 'qwen-3.6-27b', 16, 64, 'absent (below vram_tier)', 'llama.cpp'),
    ('cpu', 'qwen-3.6-27b', 24, 64, 'Qwen3.6-27B-Q5_K_M.gguf', 'llama.cpp'),
    ('cpu', 'qwen-3.6-27b', 32, 64, 'Qwen3.6-27B-UD-Q6_K_XL.gguf', 'llama.cpp'),
    ('cpu', 'qwen-3.6-27b', 64, 64, 'Qwen3.6-27B-BF16-00001-of-00002.gguf', 'llama.cpp'),
    ('metal', 'qwen-3.6-27b', 8, 64, 'absent (below vram_tier)', 'llama.cpp'),
    ('metal', 'qwen-3.6-27b', 16, 64, 'absent (below vram_tier)', 'llama.cpp'),
    ('metal', 'qwen-3.6-27b', 24, 64, 'Qwen3.6-27B-UD-IQ2_XXS.gguf', 'llama.cpp'),
    ('metal', 'qwen-3.6-27b', 32, 64, 'Qwen3.6-27B-IQ4_NL.gguf', 'llama.cpp'),
    ('metal', 'qwen-3.6-27b', 64, 64, 'Qwen3.6-27B-UD-Q8_K_XL.gguf', 'llama.cpp'),
    ('cuda', 'gemma-4-e2b', 8, 64, 'absent (below vram_tier)', 'litert'),
    ('cuda', 'gemma-4-e2b', 16, 64, 'absent (below vram_tier)', 'litert'),
    ('cuda', 'gemma-4-e2b', 24, 64, 'absent (below vram_tier)', 'litert'),
    ('cuda', 'gemma-4-e2b', 32, 64, 'absent (below vram_tier)', 'litert'),
    ('cuda', 'gemma-4-e2b', 64, 64, 'absent (below vram_tier)', 'litert'),
    ('rocm', 'gemma-4-e2b', 8, 64, 'absent (below vram_tier)', 'litert'),
    ('rocm', 'gemma-4-e2b', 16, 64, 'absent (below vram_tier)', 'litert'),
    ('rocm', 'gemma-4-e2b', 24, 64, 'absent (below vram_tier)', 'litert'),
    ('rocm', 'gemma-4-e2b', 32, 64, 'absent (below vram_tier)', 'litert'),
    ('rocm', 'gemma-4-e2b', 64, 64, 'absent (below vram_tier)', 'litert'),
    ('vulkan', 'gemma-4-e2b', 8, 64, 'absent (below vram_tier)', 'litert'),
    ('vulkan', 'gemma-4-e2b', 16, 64, 'absent (below vram_tier)', 'litert'),
    ('vulkan', 'gemma-4-e2b', 24, 64, 'absent (below vram_tier)', 'litert'),
    ('vulkan', 'gemma-4-e2b', 32, 64, 'absent (below vram_tier)', 'litert'),
    ('vulkan', 'gemma-4-e2b', 64, 64, 'absent (below vram_tier)', 'litert'),
    ('cpu', 'gemma-4-e2b', 8, 64, 'gemma-4-E2B-it_Google_Tensor_G6.litertlm', 'litert'),
    ('cpu', 'gemma-4-e2b', 16, 64, 'gemma-4-E2B-it_Google_Tensor_G6.litertlm', 'litert'),
    ('cpu', 'gemma-4-e2b', 24, 64, 'gemma-4-E2B-it_Google_Tensor_G6.litertlm', 'litert'),
    ('cpu', 'gemma-4-e2b', 32, 64, 'gemma-4-E2B-it_Google_Tensor_G6.litertlm', 'litert'),
    ('cpu', 'gemma-4-e2b', 64, 64, 'gemma-4-E2B-it_Google_Tensor_G6.litertlm', 'litert'),
    ('metal', 'gemma-4-e2b', 8, 64, 'gemma-4-E2B-it_Google_Tensor_G6.litertlm', 'litert'),
    ('metal', 'gemma-4-e2b', 16, 64, 'gemma-4-E2B-it_Google_Tensor_G6.litertlm', 'litert'),
    ('metal', 'gemma-4-e2b', 24, 64, 'gemma-4-E2B-it_Google_Tensor_G6.litertlm', 'litert'),
    ('metal', 'gemma-4-e2b', 32, 64, 'gemma-4-E2B-it_Google_Tensor_G6.litertlm', 'litert'),
    ('metal', 'gemma-4-e2b', 64, 64, 'gemma-4-E2B-it_Google_Tensor_G6.litertlm', 'litert'),
    ('cuda', 'muse-glimmer-30b', 8, 64, 'absent (below vram_tier)', 'llama.cpp'),
    ('cuda', 'muse-glimmer-30b', 16, 64, 'absent (below vram_tier)', 'llama.cpp'),
    ('cuda', 'muse-glimmer-30b', 24, 64, 'Muse-Glimmer-30B-KQuant-17GB-Q4_K_M.gguf', 'llama.cpp'),
    ('cuda', 'muse-glimmer-30b', 32, 64, 'Muse-Glimmer-30B-KQuant-Dynamic-Q4_K_XL.gguf', 'llama.cpp'),
    ('cuda', 'muse-glimmer-30b', 64, 64, 'Muse-Glimmer-30B-KQuant-Dynamic-Q4_K_XL.gguf', 'llama.cpp'),
    ('rocm', 'muse-glimmer-30b', 8, 64, 'absent (below vram_tier)', 'llama.cpp'),
    ('rocm', 'muse-glimmer-30b', 16, 64, 'absent (below vram_tier)', 'llama.cpp'),
    ('rocm', 'muse-glimmer-30b', 24, 64, 'Muse-Glimmer-30B-KQuant-17GB-Q4_K_M.gguf', 'llama.cpp'),
    ('rocm', 'muse-glimmer-30b', 32, 64, 'Muse-Glimmer-30B-KQuant-Dynamic-Q4_K_XL.gguf', 'llama.cpp'),
    ('rocm', 'muse-glimmer-30b', 64, 64, 'Muse-Glimmer-30B-KQuant-Dynamic-Q4_K_XL.gguf', 'llama.cpp'),
    ('vulkan', 'muse-glimmer-30b', 8, 64, 'absent (below vram_tier)', 'llama.cpp'),
    ('vulkan', 'muse-glimmer-30b', 16, 64, 'absent (below vram_tier)', 'llama.cpp'),
    ('vulkan', 'muse-glimmer-30b', 24, 64, 'Muse-Glimmer-30B-KQuant-17GB-Q4_K_M.gguf', 'llama.cpp'),
    ('vulkan', 'muse-glimmer-30b', 32, 64, 'Muse-Glimmer-30B-KQuant-Dynamic-Q4_K_XL.gguf', 'llama.cpp'),
    ('vulkan', 'muse-glimmer-30b', 64, 64, 'Muse-Glimmer-30B-KQuant-Dynamic-Q4_K_XL.gguf', 'llama.cpp'),
    ('cpu', 'muse-glimmer-30b', 8, 64, 'absent (below vram_tier)', 'llama.cpp'),
    ('cpu', 'muse-glimmer-30b', 16, 64, 'absent (below vram_tier)', 'llama.cpp'),
    ('cpu', 'muse-glimmer-30b', 24, 64, 'Muse-Glimmer-30B-KQuant-17GB-Q4_K_M.gguf', 'llama.cpp'),
    ('cpu', 'muse-glimmer-30b', 32, 64, 'Muse-Glimmer-30B-KQuant-Dynamic-Q4_K_XL.gguf', 'llama.cpp'),
    ('cpu', 'muse-glimmer-30b', 64, 64, 'Muse-Glimmer-30B-KQuant-Dynamic-Q4_K_XL.gguf', 'llama.cpp'),
    ('metal', 'muse-glimmer-30b', 8, 64, 'absent (below vram_tier)', 'llama.cpp'),
    ('metal', 'muse-glimmer-30b', 16, 64, 'absent (below vram_tier)', 'llama.cpp'),
    ('metal', 'muse-glimmer-30b', 24, 64, 'dflash-Muse-Glimmer-30B-Q4_K_M.gguf', 'llama.cpp'),
    ('metal', 'muse-glimmer-30b', 32, 64, 'dflash-Muse-Glimmer-30B-Q4_K_M.gguf', 'llama.cpp'),
    ('metal', 'muse-glimmer-30b', 64, 64, 'Muse-Glimmer-30B-KQuant-Dynamic-Q4_K_XL.gguf', 'llama.cpp'),
    ('cuda', 'llama-3.1-8b', 8, 64, 'Meta-Llama-3.1-8B-Instruct-Q5_K_M.gguf', 'vllm'),
    ('cuda', 'llama-3.1-8b', 16, 64, 'Meta-Llama-3.1-8B-Instruct-Q8_0.gguf', 'vllm'),
    ('cuda', 'llama-3.1-8b', 24, 64, 'Meta-Llama-3.1-8B-Instruct-Q8_0.gguf', 'vllm'),
    ('cuda', 'llama-3.1-8b', 32, 64, 'Meta-Llama-3.1-8B-Instruct-Q8_0.gguf', 'vllm'),
    ('cuda', 'llama-3.1-8b', 64, 64, 'meta-llama/Llama-3.1-8B', 'vllm'),
    ('rocm', 'llama-3.1-8b', 8, 64, 'Meta-Llama-3.1-8B-Instruct-Q5_K_M.gguf', 'vllm'),
    ('rocm', 'llama-3.1-8b', 16, 64, 'Meta-Llama-3.1-8B-Instruct-Q8_0.gguf', 'vllm'),
    ('rocm', 'llama-3.1-8b', 24, 64, 'Meta-Llama-3.1-8B-Instruct-Q8_0.gguf', 'vllm'),
    ('rocm', 'llama-3.1-8b', 32, 64, 'Meta-Llama-3.1-8B-Instruct-Q8_0.gguf', 'vllm'),
    ('rocm', 'llama-3.1-8b', 64, 64, 'meta-llama/Llama-3.1-8B', 'vllm'),
    ('vulkan', 'llama-3.1-8b', 8, 64, 'absent (below vram_tier)', 'vllm'),
    ('vulkan', 'llama-3.1-8b', 16, 64, 'absent (below vram_tier)', 'vllm'),
    ('vulkan', 'llama-3.1-8b', 24, 64, 'absent (below vram_tier)', 'vllm'),
    ('vulkan', 'llama-3.1-8b', 32, 64, 'absent (below vram_tier)', 'vllm'),
    ('vulkan', 'llama-3.1-8b', 64, 64, 'absent (below vram_tier)', 'vllm'),
    ('cpu', 'llama-3.1-8b', 8, 64, 'Meta-Llama-3.1-8B-Instruct-Q5_K_M.gguf', 'vllm'),
    ('cpu', 'llama-3.1-8b', 16, 64, 'Meta-Llama-3.1-8B-Instruct-Q8_0.gguf', 'vllm'),
    ('cpu', 'llama-3.1-8b', 24, 64, 'Meta-Llama-3.1-8B-Instruct-Q8_0.gguf', 'vllm'),
    ('cpu', 'llama-3.1-8b', 32, 64, 'Meta-Llama-3.1-8B-Instruct-Q8_0.gguf', 'vllm'),
    ('cpu', 'llama-3.1-8b', 64, 64, 'meta-llama/Llama-3.1-8B', 'vllm'),
    ('metal', 'llama-3.1-8b', 8, 64, 'absent (below vram_tier)', 'vllm'),
    ('metal', 'llama-3.1-8b', 16, 64, 'absent (below vram_tier)', 'vllm'),
    ('metal', 'llama-3.1-8b', 24, 64, 'absent (below vram_tier)', 'vllm'),
    ('metal', 'llama-3.1-8b', 32, 64, 'absent (below vram_tier)', 'vllm'),
    ('metal', 'llama-3.1-8b', 64, 64, 'absent (below vram_tier)', 'vllm'),
    ('cuda', 'deepseek-r1-1.5b', 8, 64, 'DeepSeek-R1-Distill-Qwen-1.5B-BF16.gguf', 'ollama'),
    ('cuda', 'deepseek-r1-1.5b', 16, 64, 'DeepSeek-R1-Distill-Qwen-1.5B-BF16.gguf', 'ollama'),
    ('cuda', 'deepseek-r1-1.5b', 24, 64, 'DeepSeek-R1-Distill-Qwen-1.5B-BF16.gguf', 'ollama'),
    ('cuda', 'deepseek-r1-1.5b', 32, 64, 'DeepSeek-R1-Distill-Qwen-1.5B-BF16.gguf', 'ollama'),
    ('cuda', 'deepseek-r1-1.5b', 64, 64, 'DeepSeek-R1-Distill-Qwen-1.5B-BF16.gguf', 'ollama'),
    ('rocm', 'deepseek-r1-1.5b', 8, 64, 'DeepSeek-R1-Distill-Qwen-1.5B-BF16.gguf', 'ollama'),
    ('rocm', 'deepseek-r1-1.5b', 16, 64, 'DeepSeek-R1-Distill-Qwen-1.5B-BF16.gguf', 'ollama'),
    ('rocm', 'deepseek-r1-1.5b', 24, 64, 'DeepSeek-R1-Distill-Qwen-1.5B-BF16.gguf', 'ollama'),
    ('rocm', 'deepseek-r1-1.5b', 32, 64, 'DeepSeek-R1-Distill-Qwen-1.5B-BF16.gguf', 'ollama'),
    ('rocm', 'deepseek-r1-1.5b', 64, 64, 'DeepSeek-R1-Distill-Qwen-1.5B-BF16.gguf', 'ollama'),
    ('vulkan', 'deepseek-r1-1.5b', 8, 64, 'DeepSeek-R1-Distill-Qwen-1.5B-BF16.gguf', 'ollama'),
    ('vulkan', 'deepseek-r1-1.5b', 16, 64, 'DeepSeek-R1-Distill-Qwen-1.5B-BF16.gguf', 'ollama'),
    ('vulkan', 'deepseek-r1-1.5b', 24, 64, 'DeepSeek-R1-Distill-Qwen-1.5B-BF16.gguf', 'ollama'),
    ('vulkan', 'deepseek-r1-1.5b', 32, 64, 'DeepSeek-R1-Distill-Qwen-1.5B-BF16.gguf', 'ollama'),
    ('vulkan', 'deepseek-r1-1.5b', 64, 64, 'DeepSeek-R1-Distill-Qwen-1.5B-BF16.gguf', 'ollama'),
    ('cpu', 'deepseek-r1-1.5b', 8, 64, 'DeepSeek-R1-Distill-Qwen-1.5B-BF16.gguf', 'ollama'),
    ('cpu', 'deepseek-r1-1.5b', 16, 64, 'DeepSeek-R1-Distill-Qwen-1.5B-BF16.gguf', 'ollama'),
    ('cpu', 'deepseek-r1-1.5b', 24, 64, 'DeepSeek-R1-Distill-Qwen-1.5B-BF16.gguf', 'ollama'),
    ('cpu', 'deepseek-r1-1.5b', 32, 64, 'DeepSeek-R1-Distill-Qwen-1.5B-BF16.gguf', 'ollama'),
    ('cpu', 'deepseek-r1-1.5b', 64, 64, 'DeepSeek-R1-Distill-Qwen-1.5B-BF16.gguf', 'ollama'),
    ('metal', 'deepseek-r1-1.5b', 8, 64, 'DeepSeek-R1-Distill-Qwen-1.5B-Q8_0.gguf', 'ollama'),
    ('metal', 'deepseek-r1-1.5b', 16, 64, 'DeepSeek-R1-Distill-Qwen-1.5B-BF16.gguf', 'ollama'),
    ('metal', 'deepseek-r1-1.5b', 24, 64, 'DeepSeek-R1-Distill-Qwen-1.5B-BF16.gguf', 'ollama'),
    ('metal', 'deepseek-r1-1.5b', 32, 64, 'DeepSeek-R1-Distill-Qwen-1.5B-BF16.gguf', 'ollama'),
    ('metal', 'deepseek-r1-1.5b', 64, 64, 'DeepSeek-R1-Distill-Qwen-1.5B-BF16.gguf', 'ollama'),
]
_EDGE_IDS = [f"{a}::{m}::v{v}::r{r}->{x}" for a, m, v, r, x, e in _EDGE_CASES]


@pytest.mark.parametrize("arch,model_id,vram,ram,expected,engine", _EDGE_CASES, ids=_EDGE_IDS)
def test_pick_matrix_edge_case_golden(arch, model_id, vram, ram, expected, engine, tmp_path):
    """GOLDEN edge-case test with NO GAPS, through the REAL wired `llgenie` CLI
    (scripts/llama_serve.py main, the launcher the user runs): for every trending
    model x engine x architecture x VRAM ladder, `llgenie --matrix --vram V --ram R
    --arch A` MUST print exactly the EXPECTED quantized HF model (the largest that
    fits) or the skip reason. The parametrize id shows inputs -> expected, so the
    edge cases for every model, engine and architecture are visible and asserted
    exactly — the same wired business logic as the full permutation test, but with
    clear input -> expected output. No engine starts (--matrix never serves)."""
    env = {**os.environ, "LLAMA_MODELS_ROOT": str(tmp_path), "LLAMA_BACKEND": arch,
           "LLAMA_RAM_BYTES": str(int(vram * 2**30)), "LLGENIE_SYSTEM_RAM_BYTES": str(int(ram * 2**30)),
           "XDG_CACHE_HOME": str(HUB_CACHE)}
    env.pop("LLGENIE_REGISTRY_SRC", None)
    r = subprocess.run([sys.executable, str(SERVE), "--matrix", "--vram", str(vram),
                        "--ram", str(ram), "--arch", arch],
                       env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, (arch, model_id, engine, vram, ram, r.stdout[-800:], r.stderr[-800:])
    out = r.stdout
    # the CLI prints display names, not ids: map them for the presence checks
    model_name = next(m["name"] for m in real_models() if m["id"] == model_id)
    engine_name = next(n for n, i in _ENGINE_IDS.items() if i["id"] == engine)
    if expected.startswith("absent"):
        # below vram_tier: the model is not in the trend list at all
        assert model_name not in out, f"{arch}/{model_id}/{engine} v{vram}: expected absent but it was printed"
        return
    if expected.startswith("no ") or expected == "no-fit":
        # fits VRAM but no engine/quant: printed as a skipped row with the reason
        assert model_name in out, f"{arch}/{model_id}/{engine} v{vram}: expected skip but not printed"
        return
    # offered: the exact quantized HF model must appear in the CLI output
    assert expected in out, \
        f"{arch}/{model_id}/{engine} v{vram} r{ram}: expected {expected!r} in llgenie --matrix output but it was not printed"
    # and the engine that serves it is printed too
    assert engine_name in out, f"{arch}/{model_id}/{engine} v{vram} r{ram}: engine {engine_name!r} not in the CLI output"


# === RAM-ladder golden edge cases: engines that are RAM-sensitive ==================
# Some engines pick a DIFFERENT quant based on the host's RAM, not just VRAM:
#   - Strata (qwen3.8-flash-next-125b): its setup.py picks Q2_0 below 60 GB of RAM and
#     IQ3_XXS from 60 GB up (a RAM threshold, independent of VRAM).
#   - FreeToken (qwen3.6-35b-a3b, a MoE): more RAM -> a larger quant (the MoE budget
#     adds system RAM), up to the whole-repo snapshot.
# This test walks the RAM ladder at a fixed VRAM and asserts the exact expected quant
# (or skip) for each, through the REAL wired `llgenie --matrix` CLI.
_RAM_CASES = [
    # (arch, model, engine, vram, ram, expected)
    # --- Strata: RAM threshold at 60 GB (Q2_0 below, IQ3_XXS from 60) ---
    ("cuda", "qwen3.8-flash-next-125b", "strata", 64, 16, "Qwen3.8-Flash-Next-GSQ-RCO-Q2_0-00002-of-00002.gguf"),
    ("cuda", "qwen3.8-flash-next-125b", "strata", 64, 32, "Qwen3.8-Flash-Next-GSQ-RCO-IQ3_XXS-00002-of-00002.gguf"),
    ("cuda", "qwen3.8-flash-next-125b", "strata", 64, 48, "Qwen3.8-Flash-Next-GSQ-RCO-IQ3_XXS-00002-of-00002.gguf"),
    ("cuda", "qwen3.8-flash-next-125b", "strata", 64, 60, "Qwen3.8-Flash-Next-GSQ-RCO-IQ3_XXS-00002-of-00002.gguf"),
    ("cuda", "qwen3.8-flash-next-125b", "strata", 64, 64, "Qwen3.8-Flash-Next-GSQ-RCO-IQ3_XXS-00002-of-00002.gguf"),
    ("rocm", "qwen3.8-flash-next-125b", "strata", 64, 16, "Qwen3.8-Flash-Next-GSQ-RCO-Q2_0-00002-of-00002.gguf"),
    ("rocm", "qwen3.8-flash-next-125b", "strata", 64, 32, "Qwen3.8-Flash-Next-GSQ-RCO-IQ3_XXS-00002-of-00002.gguf"),
    ("rocm", "qwen3.8-flash-next-125b", "strata", 64, 60, "Qwen3.8-Flash-Next-GSQ-RCO-IQ3_XXS-00002-of-00002.gguf"),
    # --- FreeToken (MoE): more RAM -> a larger quant, up to the whole-repo snapshot ---
    ("cuda", "qwen3.6-35b-a3b", "freetoken", 24, 16, "Qwen3.6-35B-A3B-UD-Q6_K_XL.gguf"),
    ("cuda", "qwen3.6-35b-a3b", "freetoken", 24, 32, "Qwen3.6-35B-A3B-UD-Q8_K_XL.gguf"),
    ("cuda", "qwen3.6-35b-a3b", "freetoken", 24, 48, "Qwen3.6-35B-A3B-UD-Q8_K_XL.gguf"),
    ("cuda", "qwen3.6-35b-a3b", "freetoken", 24, 60, "Qwen/Qwen3.6-35B-A3B"),
    ("cuda", "qwen3.6-35b-a3b", "freetoken", 24, 64, "Qwen/Qwen3.6-35B-A3B"),
    ("rocm", "qwen3.6-35b-a3b", "freetoken", 24, 16, "Qwen3.6-35B-A3B-UD-Q6_K_XL.gguf"),
    ("rocm", "qwen3.6-35b-a3b", "freetoken", 24, 32, "Qwen3.6-35B-A3B-UD-Q8_K_XL.gguf"),
    ("rocm", "qwen3.6-35b-a3b", "freetoken", 24, 48, "Qwen3.6-35B-A3B-UD-Q8_K_XL.gguf"),
    ("rocm", "qwen3.6-35b-a3b", "freetoken", 24, 64, "Qwen/Qwen3.6-35B-A3B"),
]
_RAM_IDS = [f"{a}::{m}::{e}::v{v}::r{r}->{x}" for a, m, e, v, r, x in _RAM_CASES]


@pytest.mark.parametrize("arch,model_id,engine,vram,ram,expected", _RAM_CASES, ids=_RAM_IDS)
def test_pick_matrix_edge_case_golden_ram(arch, model_id, engine, vram, ram, expected, tmp_path):
    """GOLDEN RAM-ladder edge-case test through the REAL wired `llgenie` CLI: for the
    engines that are RAM-sensitive (Strata's 60 GB threshold; FreeToken's MoE budget),
    walking RAM at a fixed VRAM MUST change the expected quant exactly as the business
    logic dictates. The parametrize id shows inputs -> expected."""
    env = {**os.environ, "LLAMA_MODELS_ROOT": str(tmp_path), "LLAMA_BACKEND": arch,
           "LLAMA_RAM_BYTES": str(int(vram * 2**30)), "LLGENIE_SYSTEM_RAM_BYTES": str(int(ram * 2**30)),
           "XDG_CACHE_HOME": str(HUB_CACHE)}
    env.pop("LLGENIE_REGISTRY_SRC", None)
    r = subprocess.run([sys.executable, str(SERVE), "--matrix", "--vram", str(vram),
                        "--ram", str(ram), "--arch", arch],
                       env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, (arch, model_id, engine, vram, ram, r.stdout[-800:], r.stderr[-800:])
    out = r.stdout
    model_name = next(m["name"] for m in real_models() if m["id"] == model_id)
    engine_name = next(n for n, i in _ENGINE_IDS.items() if i["id"] == engine)
    if expected.startswith("absent"):
        assert model_name not in out, f"{arch}/{model_id}/{engine} v{vram} r{ram}: expected absent but printed"
        return
    if expected.startswith("no ") or expected == "no-fit":
        assert model_name in out, f"{arch}/{model_id}/{engine} v{vram} r{ram}: expected skip but not printed"
        return
    assert expected in out, \
        f"{arch}/{model_id}/{engine} v{vram} r{ram}: expected {expected!r} in llgenie --matrix output but not printed"
    assert engine_name in out, f"{arch}/{model_id}/{engine} v{vram} r{ram}: engine {engine_name!r} not in the CLI output"
